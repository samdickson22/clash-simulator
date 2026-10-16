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
from .strategy_bots import STRATEGY_NAMES, BalancedStrategyConfig, StrategyBot
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
    card_levels: tuple[dict[str, int], dict[str, int]] | None = None
    tower_levels: tuple[int, int] = (11, 11)
    level_randomization_after: int | None = None
    mixed_level_probability: float = 0.5
    initial_learner_decisions: int = 0
    reward_potential_scale: float | None = None
    council_opponent_pool: str | None = None
    recurrent_update_mode: str = "full-prefix"
    tbptt_burn_in: int = 16
    learner_teacher_strategy: str | None = None
    learner_teacher_balanced_config: dict[str, Any] | None = None


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
        if field.name in {"recurrent_prefixes", "burn_in_prefixes"} and values[0] is not None:
            if any(value is None for value in values):
                raise ValueError("parallel rollout mixes recurrent prefix contracts")
            payload[field.name] = tuple(item for value in values for item in value)
        elif isinstance(values[0], np.ndarray):
            payload[field.name] = np.concatenate(values, axis=0)
        elif values[0] is None:
            if any(value is not None for value in values):
                raise ValueError(
                    f"parallel rollout field {field.name} mixes absent and present data"
                )
            payload[field.name] = None
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
        "public_contract_version",
        "public_history_slots",
        "public_seen_card_slots",
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
    builder = StructuredObservationBuilder(
        decks_path=decks_path,
        card_vocab=card_vocab,
        max_entities=config.max_entities,
        token_names=token_names,
        card_semantics_version=config.card_semantics_version,
        canonical_lane_globals=config.canonical_lane_globals,
        public_history_slots=config.public_history_slots,
        public_seen_card_slots=config.public_seen_card_slots,
        public_entity_levels=config.public_contract_version >= 3,
        public_hand_levels=config.public_contract_version >= 4,
    )

    builder.public_contract_version = config.public_contract_version
    return builder


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
        learner_teacher_bot: StrategyBot | None = None
        if config.learner_teacher_strategy is not None:
            teacher_config = (
                BalancedStrategyConfig(**config.learner_teacher_balanced_config)
                if config.learner_teacher_balanced_config is not None
                else BalancedStrategyConfig()
            )
            learner_teacher_bot = StrategyBot(
                config.learner_teacher_strategy,
                balanced_config=teacher_config,
            )
        if opponent_spec is not None and opponent_spec.kind == "checkpoint":
            assert opponent_spec.checkpoint is not None
            opponent_model = load_checkpoint_opponent(
                opponent_spec.checkpoint,
                device=device,
                builder=builder,
                learner_config=policy_config,
                token_names=config.token_names,
            )

        if config.council_opponent_pool is not None:
            from .council_opponents import CouncilLeagueOpponent

            if config.opponent_mode != "strategy":
                raise ValueError(
                    "council pool requires the stationary opponent collector"
                )
            opponent_bot = CouncilLeagueOpponent(
                builder=builder,
                learner_model=model,
                pool_path=config.council_opponent_pool,
                seed=config.base_seed + 97 * worker_id,
                worker_id=worker_id,
                assignment_log=Path(config.council_opponent_pool).parent
                / f"worker-{worker_id}-assignments.jsonl",
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
                    public_contract_version=policy_config.public_contract_version,
                    card_levels=config.card_levels,
                    tower_levels=config.tower_levels,
                    level_randomization_after=config.level_randomization_after,
                    mixed_level_probability=config.mixed_level_probability,
                    reward_potential_scale=config.reward_potential_scale,
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
                env.set_learner_decisions(config.initial_learner_decisions)
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
            _, policy_version, rollout_steps, state_dict, learner_decisions = command
            for env in envs:
                env.set_learner_decisions(learner_decisions)
            model.load_state_dict(state_dict)
            if config.council_opponent_pool is not None:
                opponent_bot.set_context(
                    policy_version=int(policy_version),
                    learner_decisions=learner_decisions,
                )
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
                    recurrent_update_mode=config.recurrent_update_mode,
                    tbptt_burn_in=config.tbptt_burn_in,
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
                    learner_teacher_bot=learner_teacher_bot,
                    opponent_noop=(
                        opponent_spec is not None and opponent_spec.kind == "noop"
                    ),
                    hazard_conditioned_rollouts=(config.hazard_conditioned_rollouts),
                )
                if stationary_opponents
                else collect_rollout(
                    envs=envs,
                    builder=builder,
                    model=model,
                    device=device,
                    rollout_steps=int(rollout_steps),
                    recurrent_update_mode=config.recurrent_update_mode,
                    tbptt_burn_in=config.tbptt_burn_in,
                    recurrent_state=recurrent_state,
                    previous_actions=previous_actions,
                    previous_rewards=previous_rewards,
                    episode_starts=episode_starts,
                    quiet_engine=config.quiet_engine,
                    hazard_conditioned_rollouts=(config.hazard_conditioned_rollouts),
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
        learner_decisions: int = 0,
        timeout: float = 600.0,
    ) -> RolloutBatch:
        if self._closed:
            raise RuntimeError("parallel rollout collector is closed")
        state_dict = _cpu_state_dict(model)
        for command_queue in self._command_queues:
            command_queue.put(
                (
                    "collect",
                    policy_version,
                    rollout_steps,
                    state_dict,
                    learner_decisions,
                )
            )

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


# ---------------------------------------------------------------------------
# Learner-side batched inference (council admission-scope decision v1).
#
# Actor processes own the simulators and the scripted/frozen opponents. The
# learner owns the policy: each decision it runs one batched forward over every
# environment, samples with its own Torch RNG, and keeps the recurrent carry and
# the exact episode-prefix history. Environments are addressed by their global
# index and returned in that order, so the collected rollout does not depend on
# how environments are partitioned across actor processes. Opponents are
# instantiated per environment (seeded by the global index) for the same reason.
# The per-environment step below reproduces ``collect_rollout_stationary_opponents``
# call for call: learner observation and mask, then opponent masks, opponent
# actions, the simulator step, the truncation observation and the reset.
# ---------------------------------------------------------------------------

LEARNER_INFERENCE_OPPONENT_SEED_STRIDE = 1_000_081
LEARNER_INFERENCE_OPPONENT_CACHE = 8


@dataclass
class EnvSlot:
    """One environment addressed by its global index, with its own opponent."""

    env_index: int
    env: SelfPlayBattleEnv
    learner_player: int
    opponent_kind: Literal["bot", "noop", "random"]
    opponent: Any | None = None


@dataclass
class SlotStepResult:
    reward: float
    done: bool
    action_success: bool
    learner_result: Literal["win", "loss", "draw"] | None
    truncation_observation: Any | None = None
    truncation_mask: np.ndarray | None = None


def build_actor_environment(
    config: ActorWorkerConfig,
    env_index: int,
    policy_config: PolicyConfig,
    builder: StructuredObservationBuilder,
) -> SelfPlayBattleEnv:
    """The environment ``_actor_worker_main`` builds for this global index."""
    seed = config.base_seed + env_index * 1009
    learner_player = env_index % 2
    player_sampling_paths = (
        (config.learner_sampling_decks_path, config.opponent_sampling_decks_path)
        if learner_player == 0
        else (config.opponent_sampling_decks_path, config.learner_sampling_decks_path)
    )
    env = SelfPlayBattleEnv(
        public_contract_version=policy_config.public_contract_version,
        card_levels=config.card_levels,
        tower_levels=config.tower_levels,
        level_randomization_after=config.level_randomization_after,
        mixed_level_probability=config.mixed_level_probability,
        reward_potential_scale=config.reward_potential_scale,
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
        defense_scenario_minimum_elixir=config.defense_scenario_minimum_elixir,
        defense_scenario_maximum_elixir=config.defense_scenario_maximum_elixir,
        defense_scenario_horizon_ticks=config.defense_scenario_horizon_ticks,
        defense_scenario_reward_scale=config.defense_scenario_reward_scale,
    )
    env._structured_obs_builder = builder
    env.set_learner_decisions(config.initial_learner_decisions)
    env.reset(seed=seed)
    return env


def build_environment_opponents(
    config: ActorWorkerConfig,
    env_indices: tuple[int, ...],
    *,
    builder: StructuredObservationBuilder,
    learner_model: ClasherPolicy,
) -> list[tuple[Literal["bot", "noop", "random"], Any | None]]:
    """One opponent per environment, seeded by the global environment index."""
    if config.learner_teacher_strategy is not None:
        raise ValueError("learner-side inference does not collect teacher labels")
    if config.opponent_mode not in {"noop", "random", "strategy"}:
        raise ValueError(
            "learner-side inference supports noop, random, strategy and council opponents"
        )
    if config.council_opponent_pool is None and config.opponent_mode == "strategy":
        strategies = {spec.strategy for spec in config.opponent_pool}
        if len(config.opponent_pool) != 1 or None in strategies:
            raise ValueError("learner-side inference needs exactly one strategy opponent")
    opponents: list[tuple[Literal["bot", "noop", "random"], Any | None]] = []
    shared_cache: Any = None
    for env_index in env_indices:
        if config.council_opponent_pool is not None:
            from collections import OrderedDict

            from .council_opponents import CouncilLeagueOpponent

            if config.opponent_mode != "strategy":
                raise ValueError(
                    "council pool requires the stationary opponent collector"
                )
            opponent = CouncilLeagueOpponent(
                builder=builder,
                learner_model=learner_model,
                pool_path=config.council_opponent_pool,
                seed=config.base_seed
                + LEARNER_INFERENCE_OPPONENT_SEED_STRIDE * (env_index + 1),
                worker_id=env_index,
                assignment_log=Path(config.council_opponent_pool).parent
                / f"worker-env{env_index:03d}-assignments.jsonl",
                checkpoint_cache_size=LEARNER_INFERENCE_OPPONENT_CACHE,
            )
            # Frozen opponent weights are read-only; one cache per process keeps
            # memory flat. Each episode still holds its own recurrent state and
            # sampling RNG, and every load re-verifies the checkpoint digest.
            if shared_cache is None:
                shared_cache = OrderedDict()
            opponent._models = shared_cache
            opponents.append(("bot", opponent))
        elif config.opponent_mode == "strategy":
            opponents.append(("bot", StrategyBot(config.opponent_pool[0].strategy)))
        else:
            opponents.append((config.opponent_mode, None))  # type: ignore[arg-type]
    return opponents


def observe_slots(
    slots: list[EnvSlot], *, actor_observation_domain: str, quiet_engine: bool
) -> tuple[list[Any], list[np.ndarray]]:
    observations: list[Any] = []
    masks: list[np.ndarray] = []
    with maybe_silence_stdio(quiet_engine):
        for slot in slots:
            observation = slot.env.get_structured_observation(
                slot.learner_player,
                actor_observation_domain=actor_observation_domain,
            )
            observations.append(observation)
            masks.append(
                slot.env.get_action_mask(
                    slot.learner_player,
                    actor_observation_domain=actor_observation_domain,
                    structured_observation=observation,
                )
            )
    return observations, masks


def step_slots(
    slots: list[EnvSlot],
    actions: np.ndarray,
    learner_masks: list[np.ndarray],
    *,
    actor_observation_domain: str,
    quiet_engine: bool,
    truncation_bootstrap: bool,
) -> list[SlotStepResult]:
    """Opponent masks, opponent actions and one simulator step per environment."""
    if len(actions) != len(slots) or len(learner_masks) != len(slots):
        raise ValueError("one learner action and mask are required per environment")
    results: list[SlotStepResult] = []
    with maybe_silence_stdio(quiet_engine):
        opponent_masks = [
            slot.env.get_action_mask(1 - slot.learner_player) for slot in slots
        ]
        opponent_actions: list[int] = []
        for slot, mask in zip(slots, opponent_masks):
            no_op = slot.env.action_space.no_op_action
            if slot.opponent_kind == "noop":
                opponent_actions.append(no_op)
            elif slot.opponent_kind == "bot":
                opponent_actions.append(
                    int(
                        slot.opponent.select_action(
                            slot.env, 1 - slot.learner_player, action_mask=mask
                        )
                    )
                )
            else:
                opponent_actions.append(
                    int(slot.env.np_rng.choice(np.flatnonzero(mask)))
                    if np.any(mask)
                    else no_op
                )
        for index, slot in enumerate(slots):
            if slot.env.defense_scenario is not None:
                opponent_actions[index] = slot.env.action_space.no_op_action
        for slot, action, learner_mask, opponent_action, opponent_mask in zip(
            slots, actions, learner_masks, opponent_actions, opponent_masks
        ):
            env = slot.env
            learner_player = slot.learner_player
            opponent_player = 1 - learner_player
            rewards, done, step_info = env.step(
                {learner_player: int(action), opponent_player: int(opponent_action)},
                pre_action_masks={
                    learner_player: learner_mask,
                    opponent_player: opponent_mask,
                },
            )
            result = SlotStepResult(
                reward=float(rewards[learner_player]),
                done=bool(done),
                action_success=bool(step_info.action_success[learner_player]),
                learner_result=None,
            )
            if done and step_info.truncated and truncation_bootstrap:
                observation = env.get_structured_observation(
                    learner_player, actor_observation_domain=actor_observation_domain
                )
                result.truncation_observation = observation
                result.truncation_mask = env.get_action_mask(
                    learner_player,
                    actor_observation_domain=actor_observation_domain,
                    structured_observation=observation,
                )
            if done:
                assert env.battle is not None
                if env.battle.winner is None:
                    result.learner_result = "draw"
                elif env.battle.winner == learner_player:
                    result.learner_result = "win"
                else:
                    result.learner_result = "loss"
                record_outcome = getattr(slot.opponent, "record_outcome", None)
                if record_outcome is not None:
                    # Monitoring-only per-opponent outcome log.
                    record_outcome(env, learner_player)
                env.reset()
            results.append(result)
    return results


class LocalSlotBackend:
    """In-process environments for the learner-side collector (reference path)."""

    def __init__(
        self,
        slots: list[EnvSlot],
        *,
        actor_observation_domain: str = "simulator-exact",
        quiet_engine: bool = True,
        truncation_bootstrap: bool = True,
    ) -> None:
        if [slot.env_index for slot in slots] != list(range(len(slots))):
            raise ValueError("slots must be ordered by their global environment index")
        self.slots = slots
        self.domain = actor_observation_domain
        self.quiet_engine = quiet_engine
        self.truncation_bootstrap = truncation_bootstrap
        self._masks: list[np.ndarray] | None = None

    @property
    def num_envs(self) -> int:
        return len(self.slots)

    @property
    def num_actions(self) -> int:
        return int(self.slots[0].env.action_space.num_actions)

    @property
    def no_op_action(self) -> int:
        return int(self.slots[0].env.action_space.no_op_action)

    @property
    def public_contract_versions(self) -> set[int]:
        return {int(slot.env.public_contract_version) for slot in self.slots}

    def begin(
        self, *, policy_version: int, learner_decisions: int, state_dict: Any = None
    ) -> tuple[list[Any], list[np.ndarray]]:
        for slot in self.slots:
            slot.env.set_learner_decisions(learner_decisions)
            set_context = getattr(slot.opponent, "set_context", None)
            if set_context is not None:
                set_context(
                    policy_version=int(policy_version),
                    learner_decisions=learner_decisions,
                )
        observations, self._masks = observe_slots(
            self.slots,
            actor_observation_domain=self.domain,
            quiet_engine=self.quiet_engine,
        )
        return observations, self._masks

    def step(
        self, actions: np.ndarray
    ) -> tuple[list[SlotStepResult], list[Any], list[np.ndarray]]:
        if self._masks is None:
            raise RuntimeError("begin() must precede step()")
        results = step_slots(
            self.slots,
            actions,
            self._masks,
            actor_observation_domain=self.domain,
            quiet_engine=self.quiet_engine,
            truncation_bootstrap=self.truncation_bootstrap,
        )
        observations, self._masks = observe_slots(
            self.slots,
            actor_observation_domain=self.domain,
            quiet_engine=self.quiet_engine,
        )
        return results, observations, self._masks

    def close(self) -> None:
        return None


def _environment_worker_main(
    worker_id: int,
    env_indices: tuple[int, ...],
    config: ActorWorkerConfig,
    truncation_bootstrap: bool,
    connection: Any,
) -> None:
    try:
        torch.set_num_threads(max(1, config.torch_threads))
        torch.manual_seed(config.base_seed + 1_000_003 * (worker_id + 1))
        np.random.seed(config.base_seed + 1_000_033 * (worker_id + 1))
        policy_config = PolicyConfig.from_dict(config.model_config)
        builder = build_policy_observation_builder(
            policy_config,
            decks_path=config.decks_path,
            token_names=config.token_names,
        )
        # CPU copy of the learner weights: council opponents validate the actor
        # contract against it and copy it for current-policy matches.
        model = ClasherPolicy(policy_config, builder.card_stat_features).eval()
        with maybe_silence_stdio(config.quiet_engine):
            envs = [
                build_actor_environment(config, index, policy_config, builder)
                for index in env_indices
            ]
        opponents = build_environment_opponents(
            config, env_indices, builder=builder, learner_model=model
        )
        slots = [
            EnvSlot(
                env_index=index,
                env=env,
                learner_player=index % 2,
                opponent_kind=kind,
                opponent=opponent,
            )
            for index, env, (kind, opponent) in zip(env_indices, envs, opponents)
        ]
        domain = policy_config.actor_observation_domain
        masks: list[np.ndarray] | None = None
        connection.send(("ready", worker_id, None))
        while True:
            command = connection.recv()
            if command[0] == "close":
                return
            if command[0] == "begin":
                _, policy_version, learner_decisions, state_dict = command
                model.load_state_dict(state_dict)
                for slot in slots:
                    slot.env.set_learner_decisions(learner_decisions)
                    set_context = getattr(slot.opponent, "set_context", None)
                    if set_context is not None:
                        set_context(
                            policy_version=int(policy_version),
                            learner_decisions=learner_decisions,
                        )
                observations, masks = observe_slots(
                    slots,
                    actor_observation_domain=domain,
                    quiet_engine=config.quiet_engine,
                )
                connection.send(("observed", worker_id, (observations, masks)))
            elif command[0] == "step":
                if masks is None:
                    raise RuntimeError("begin must precede step")
                results = step_slots(
                    slots,
                    command[1],
                    masks,
                    actor_observation_domain=domain,
                    quiet_engine=config.quiet_engine,
                    truncation_bootstrap=truncation_bootstrap,
                )
                observations, masks = observe_slots(
                    slots,
                    actor_observation_domain=domain,
                    quiet_engine=config.quiet_engine,
                )
                connection.send(("stepped", worker_id, (results, observations, masks)))
            else:
                raise ValueError(f"unknown environment worker command {command[0]!r}")
    except BaseException:  # noqa: BLE001 - worker failures must reach the parent
        try:
            connection.send(("error", worker_id, traceback.format_exc()))
        except Exception:  # noqa: BLE001
            pass


class ProcessSlotBackend:
    """Actor processes that own environments; the learner owns the policy."""

    def __init__(
        self,
        *,
        num_workers: int,
        num_envs: int,
        config: ActorWorkerConfig,
        truncation_bootstrap: bool = True,
        startup_timeout: float = 180.0,
    ) -> None:
        if num_workers < 1 or num_workers > num_envs:
            raise ValueError("num_workers must be between one and num_envs")
        self.num_workers = int(num_workers)
        self._num_envs = int(num_envs)
        self._closed = False
        policy_config = PolicyConfig.from_dict(config.model_config)
        self._num_actions: int | None = None
        self._no_op: int | None = None
        self._contract = policy_config.public_contract_version
        context = mp.get_context("spawn")
        self.assignments = [
            tuple(range(worker_id, num_envs, num_workers))
            for worker_id in range(num_workers)
        ]
        self._connections: list[Any] = []
        self._processes: list[Any] = []
        for worker_id, env_indices in enumerate(self.assignments):
            parent, child = context.Pipe(duplex=True)
            process = context.Process(
                target=_environment_worker_main,
                args=(worker_id, env_indices, config, truncation_bootstrap, child),
                name=f"clasher-env-actor-{worker_id}",
                daemon=True,
            )
            process.start()
            child.close()
            self._connections.append(parent)
            self._processes.append(process)
        try:
            for worker_id in range(num_workers):
                self._receive(worker_id, "ready", startup_timeout)
        except BaseException:
            self.close(force=True)
            raise

    @property
    def num_envs(self) -> int:
        return self._num_envs

    @property
    def num_actions(self) -> int:
        if self._num_actions is None:
            raise RuntimeError("begin() must run before the action count is known")
        return self._num_actions

    @property
    def no_op_action(self) -> int:
        if self._no_op is None:
            raise RuntimeError("begin() must run before the no-op action is known")
        return self._no_op

    @property
    def public_contract_versions(self) -> set[int]:
        return {int(self._contract)}

    def _receive(self, worker_id: int, expected: str, timeout: float) -> Any:
        connection = self._connections[worker_id]
        if not connection.poll(timeout):
            dead = [p.name for p in self._processes if not p.is_alive()]
            raise TimeoutError(
                f"timed out waiting for environment actor {worker_id}; dead={dead}"
            )
        message = connection.recv()
        if message[0] == "error":
            raise RuntimeError(f"environment actor {message[1]} failed:\n{message[2]}")
        if message[0] != expected or int(message[1]) != worker_id:
            raise RuntimeError(f"unexpected environment actor message {message[0]!r}")
        return message[2]

    def _scatter(self, per_worker: list[tuple], timeout: float) -> list[Any]:
        items: list[Any] = [None] * self._num_envs
        for worker_id, env_indices in enumerate(self.assignments):
            for offset, env_index in enumerate(env_indices):
                items[env_index] = tuple(part[offset] for part in per_worker[worker_id])
        return items

    def begin(
        self, *, policy_version: int, learner_decisions: int, state_dict: Any
    ) -> tuple[list[Any], list[np.ndarray]]:
        if self._closed:
            raise RuntimeError("environment actors are closed")
        for connection in self._connections:
            connection.send(("begin", policy_version, learner_decisions, state_dict))
        replies = [
            self._receive(worker_id, "observed", 600.0)
            for worker_id in range(self.num_workers)
        ]
        merged = self._scatter(replies, 600.0)
        observations = [item[0] for item in merged]
        masks = [item[1] for item in merged]
        self._num_actions = int(masks[0].shape[-1])
        self._no_op = self._num_actions - 2
        return observations, masks

    def step(
        self, actions: np.ndarray, *, timeout: float = 600.0
    ) -> tuple[list[SlotStepResult], list[Any], list[np.ndarray]]:
        actions = np.asarray(actions, dtype=np.int64)
        for worker_id, env_indices in enumerate(self.assignments):
            self._connections[worker_id].send(
                ("step", actions[np.asarray(env_indices, dtype=np.int64)])
            )
        replies = [
            self._receive(worker_id, "stepped", timeout)
            for worker_id in range(self.num_workers)
        ]
        merged = self._scatter(replies, timeout)
        return (
            [item[0] for item in merged],
            [item[1] for item in merged],
            [item[2] for item in merged],
        )

    def close(self, *, force: bool = False) -> None:
        if self._closed:
            return
        self._closed = True
        if not force:
            for connection in self._connections:
                try:
                    connection.send(("close",))
                except (BrokenPipeError, OSError):
                    pass
        for process in self._processes:
            process.join(timeout=5.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5.0)
        for connection in self._connections:
            connection.close()


class BatchedInferenceCollector:
    """Synchronous learner-side inference over every environment per decision.

    ``backend`` is a ``ProcessSlotBackend`` (actor processes) or a
    ``LocalSlotBackend`` (in-process reference). The collector owns the learner
    recurrent carry and the exact episode-prefix history across rollouts.
    """

    def __init__(self, backend: Any, *, builder: StructuredObservationBuilder,
                 recurrent_update_mode: str = "full-prefix", tbptt_burn_in: int = 16) -> None:
        self.recurrent_update_mode = recurrent_update_mode
        self.tbptt_burn_in = tbptt_burn_in
        self.backend = backend
        self.builder = builder
        self._carry: dict[str, Any] | None = None

    @classmethod
    def with_actor_processes(
        cls,
        *,
        num_workers: int,
        num_envs: int,
        config: ActorWorkerConfig,
        builder: StructuredObservationBuilder,
        startup_timeout: float = 180.0,
    ) -> "BatchedInferenceCollector":
        policy_config = PolicyConfig.from_dict(config.model_config)
        backend = ProcessSlotBackend(
            num_workers=num_workers,
            num_envs=num_envs,
            config=config,
            truncation_bootstrap=policy_config.public_contract_version >= 4,
            startup_timeout=startup_timeout,
        )
        return cls(backend, builder=builder, recurrent_update_mode=config.recurrent_update_mode,
                   tbptt_burn_in=config.tbptt_burn_in)

    def collect(
        self,
        *,
        model: ClasherPolicy,
        rollout_steps: int,
        policy_version: int,
        learner_decisions: int = 0,
        quiet_engine: bool = True,
        hazard_conditioned_rollouts: bool = False,
    ) -> RolloutBatch:
        from .train_recurrent import collect_rollout_learner_inference

        device = next(model.parameters()).device
        agents = self.backend.num_envs
        if self._carry is None:
            self._carry = {
                "recurrent_state": model.initial_state(agents, device=device),
                "previous_actions": np.full(
                    (agents,), model.num_actions - 2, dtype=np.int64
                ),
                "previous_rewards": np.zeros((agents,), dtype=np.float32),
                "episode_starts": np.ones((agents,), dtype=np.bool_),
                "history": None,
            }
        rollout, carry = collect_rollout_learner_inference(
            backend=self.backend,
            builder=self.builder,
            model=model,
            device=device,
            rollout_steps=rollout_steps,
            carry=self._carry,
            recurrent_update_mode=self.recurrent_update_mode,
            tbptt_burn_in=self.tbptt_burn_in,
            policy_version=policy_version,
            learner_decisions=learner_decisions,
            state_dict=_cpu_state_dict(model),
            quiet_engine=quiet_engine,
            hazard_conditioned_rollouts=hazard_conditioned_rollouts,
        )
        self._carry = carry
        return rollout

    def close(self, *, force: bool = False) -> None:
        close = getattr(self.backend, "close")
        try:
            close(force=force)
        except TypeError:
            close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()
