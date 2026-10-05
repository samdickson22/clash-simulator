from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from types import SimpleNamespace

import numpy as np
import torch
from torch import nn

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path

from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from .dagger_behavior import (
    actor_policy_action,
    behavior_player_for_episode,
    parse_stationary_opponent,
    prepare_behavior_decision,
    stationary_action,
)
from .eval import load_policy_checkpoint
from .hierarchical_imitation import (
    HierarchicalImitationConfig,
    factor_public_action_mask,
    hierarchical_imitation_metric_sums,
    hierarchical_masked_imitation_loss,
    labels_from_flat_actions,
)
from .human_context import visible_enemy_pressure_mask
from .imitation_objective import (
    PLACEMENT_ACTIONS,
    SpatialImitationConfig,
    TokenSpatialSemantics,
    build_token_spatial_semantics,
    factorized_spatial_imitation_loss,
    imitation_metric_sums,
)
from .model import ClasherPolicy, PolicyConfig, PolicyInputs
from .oracle_corpus import (
    CorpusShardSpec,
    atomic_save_npz,
    corpus_fingerprint,
    file_sha256,
    load_shard,
    publish_manifest,
    publish_shard,
    reusable_shard,
    shard_path,
)
from .oracle_planner import FixedDepthThompsonOracle
from .public_action_mask import PUBLIC_ACTION_MASK_CONTRACT_VERSION
from .public_observation import (
    ENTITY_FEATURE_NAMES,
    GLOBAL_FEATURE_NAMES,
    REAL_PLAY_ENTITY_FEATURE_INDICES,
    REAL_PLAY_FEATURE_CONTRACT_VERSION,
    REAL_PLAY_GLOBAL_FEATURE_INDICES,
)
from .reward_model import DEFENSE_V2, REWARD_PROFILES
from .selfplay_env import SelfPlayBattleEnv
from .structured_obs import (
    VISIBLE_CARD_SLOTS,
    ActorObservation,
    StructuredObservation,
    StructuredObservationBuilder,
)
from .train_recurrent import (
    maybe_silence_stdio,
    policy_anchor_kl,
    resolve_learner_device,
)

CORPUS_SCHEMA_VERSION = 1
PUBLIC_OBSERVATION_SCHEMA_VERSION = 2
TYPE_HEAD_OBJECTIVE = "type-head-v1"
HIERARCHICAL_OBJECTIVE = "hierarchical-v1"
SAFE_SLOT_CHOICE_OBJECTIVE = "safe-slot-choice-v1"
SEMANTIC_SLOT_CHOICE_OBJECTIVE = "semantic-slot-choice-v1"
SLOT_CHOICE_OBJECTIVES = (
    SAFE_SLOT_CHOICE_OBJECTIVE,
    SEMANTIC_SLOT_CHOICE_OBJECTIVE,
)
IMITATION_OBJECTIVES = (
    "exact",
    "spatial-v1",
    HIERARCHICAL_OBJECTIVE,
    TYPE_HEAD_OBJECTIVE,
    SAFE_SLOT_CHOICE_OBJECTIVE,
    SEMANTIC_SLOT_CHOICE_OBJECTIVE,
)
STATIONARY_RNG_OFFSET = 15_485_863
LABEL_SOURCES = ("oracle", "behavior", "strategy")
PUBLIC_CONFIDENCE_STATE_KEYS = frozenset(
    f"actor_encoder.{scope}_confidence_projection.{layer}.{parameter}"
    for scope in ("card", "entity", "global")
    for layer in (0, 2)
    for parameter in ("bias", "weight")
)


@dataclass(frozen=True)
class CorpusMetadata:
    schema_version: int
    created_at: str
    seed: int
    decisions: int
    samples: int
    decision_interval: int
    max_ticks: int
    planner_depth: int
    planner_simulations: int
    planner_action_samples: int
    max_entities: int
    token_names: tuple[str, ...]
    reward_profile: str = DEFENSE_V2
    workers: int = 1
    behavior_checkpoint: str | None = None
    expert_probability: float = 1.0
    stable_root_candidates: bool = False
    behavior_opponent: str | None = None
    label_source: str = "oracle"
    label_strategy: str | None = None
    label_checkpoint: str | None = None
    label_checkpoint_sha256: str | None = None
    sampling_decks_path: str | None = None
    public_contract_version: int = 0
    public_history_slots: int = 0
    public_seen_card_slots: int = 0
    provenance: str | None = None

    def to_json(self) -> str:
        payload = self.__dict__.copy()
        payload["token_names"] = list(self.token_names)
        return json.dumps(payload, sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> CorpusMetadata:
        values = json.loads(payload)
        values["token_names"] = tuple(values["token_names"])
        values.setdefault("reward_profile", DEFENSE_V2)
        values.setdefault("workers", 1)
        values.setdefault("behavior_checkpoint", None)
        values.setdefault("expert_probability", 1.0)
        values.setdefault("stable_root_candidates", False)
        values.setdefault("behavior_opponent", None)
        values.setdefault("label_source", "oracle")
        values.setdefault("label_strategy", None)
        values.setdefault("label_checkpoint", None)
        values.setdefault("label_checkpoint_sha256", None)
        values.setdefault("sampling_decks_path", None)
        return cls(**values)


@dataclass(frozen=True)
class _CorpusShardConfig:
    decks_path: Path
    sampling_decks_path: Path | None
    decisions: int
    seed: int
    decision_interval: int
    max_ticks: int
    planner_depth: int
    planner_simulations: int
    planner_action_samples: int
    max_entities: int
    quiet_engine: bool
    reward_profile: str
    behavior_checkpoint: Path | None
    expert_probability: float
    stable_root_candidates: bool
    behavior_opponent: str | None
    label_source: str
    label_strategy: str | None
    shard_spec: CorpusShardSpec
    shard_path: Path


def _append_observation(
    arrays: dict[str, list[np.ndarray | int | float | bool]],
    observation: StructuredObservation | ActorObservation,
    action_mask: np.ndarray,
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
    expert_action: int,
    episode_id: int,
) -> None:
    for name in (
        "entity_ids",
        "entity_features",
        "entity_mask",
        "hand_ids",
        "global_features",
    ):
        arrays[name].append(getattr(observation, name).copy())
    arrays["action_masks"].append(action_mask.astype(np.bool_, copy=True))
    arrays["previous_actions"].append(int(previous_action))
    arrays["previous_rewards"].append(float(previous_reward))
    arrays["episode_starts"].append(bool(episode_start))
    arrays["expert_actions"].append(int(expert_action))
    arrays["episode_ids"].append(int(episode_id))


def _collect_oracle_shard(
    config: _CorpusShardConfig,
) -> dict[str, np.ndarray]:
    behavior = (
        load_policy_checkpoint(
            config.behavior_checkpoint,
            device=torch.device("cpu"),
            decks_path=config.decks_path,
        )
        if config.behavior_checkpoint is not None
        else None
    )
    if behavior is None:
        builder = StructuredObservationBuilder(
            decks_path=config.decks_path,
            max_entities=config.max_entities,
        )
    else:
        builder = behavior.builder
        if builder.spec.max_entities != config.max_entities:
            raise ValueError("behavior checkpoint max_entities does not match corpus")
    env = SelfPlayBattleEnv(
        decision_interval_ticks=config.decision_interval,
        max_ticks=config.max_ticks,
        decks_path=config.decks_path,
        sampling_decks_path=config.sampling_decks_path,
        seed=config.seed,
        canonical_perspective=True,
        reward_profile=config.reward_profile,
    )
    env._structured_obs_builder = builder
    with maybe_silence_stdio(config.quiet_engine):
        env.reset(seed=config.seed)
    planner = (
        FixedDepthThompsonOracle(
            action_space=env.action_space,
            decision_interval_ticks=config.decision_interval,
            plan_depth=config.planner_depth,
            num_simulations=config.planner_simulations,
            rollout_action_samples=config.planner_action_samples,
            seed=config.seed + 7919,
            reward_profile=config.reward_profile,
            stable_root_candidates=config.stable_root_candidates,
        )
        if config.label_source == "oracle"
        else None
    )
    behavior_states = (
        [behavior.model.initial_state(1, device=torch.device("cpu")) for _ in range(2)]
        if behavior is not None
        else None
    )
    behavior_rng = np.random.default_rng(config.seed + 104_729)
    stationary_rng = np.random.default_rng(config.seed + STATIONARY_RNG_OFFSET)
    stationary_bot = (
        parse_stationary_opponent(config.behavior_opponent)
        if config.behavior_opponent is not None
        else None
    )
    label_strategy_bot = (
        parse_stationary_opponent(config.label_strategy)
        if config.label_strategy is not None
        else None
    )
    label_strategy_rng = np.random.default_rng(config.seed + 31_415_927)
    arrays: dict[str, list[np.ndarray | int | float | bool]] = {
        name: []
        for name in (
            "entity_ids",
            "entity_features",
            "entity_mask",
            "hand_ids",
            "global_features",
            "action_masks",
            "previous_actions",
            "previous_rewards",
            "episode_starts",
            "expert_actions",
            "episode_ids",
        )
    }
    previous_actions = [env.action_space.no_op_action] * 2
    previous_rewards = [0.0, 0.0]
    episode_starts = [True, True]
    episode_id = 0
    for _ in range(config.decisions):
        assert env.battle is not None
        with maybe_silence_stdio(config.quiet_engine):
            behavior_player = (
                behavior_player_for_episode(
                    config.shard_spec.shard_index,
                    episode_id,
                )
                if config.behavior_opponent is not None
                else None
            )
            observation_players = (
                (behavior_player,) if behavior_player is not None else (0, 1)
            )
            prepared = prepare_behavior_decision(
                env,
                builder,
                observation_players=observation_players,
            )
        behavior_actions: dict[int, int] = {}
        if behavior is not None and behavior_states is not None:
            for player_id in observation_players:
                action, next_state = actor_policy_action(
                    behavior.model,
                    prepared.observations[player_id],
                    prepared.action_masks[player_id],
                    state=behavior_states[player_id],
                    previous_action=previous_actions[player_id],
                    previous_reward=previous_rewards[player_id],
                    episode_start=episode_starts[player_id],
                    deterministic=True,
                    device=torch.device("cpu"),
                )
                behavior_actions[player_id] = action
                behavior_states[player_id] = next_state
        if planner is not None:
            label_actions = planner.select_actions(env.battle)
        elif label_strategy_bot is not None:
            label_actions = {
                player_id: stationary_action(
                    env,
                    player_id,
                    prepared.action_masks[player_id],
                    rng=label_strategy_rng,
                    strategy_bot=label_strategy_bot,
                )
                for player_id in observation_players
            }
        else:
            label_actions = behavior_actions
        for player_id in observation_players:
            _append_observation(
                arrays,
                prepared.observations[player_id],
                prepared.action_masks[player_id],
                previous_actions[player_id],
                previous_rewards[player_id],
                episode_starts[player_id],
                label_actions[player_id],
                episode_id,
            )
        if behavior_player is None:
            executed_actions = {
                player_id: (
                    label_actions[player_id]
                    if behavior is None
                    or behavior_rng.random() < config.expert_probability
                    else behavior_actions[player_id]
                )
                for player_id in (0, 1)
            }
        else:
            opponent_player = 1 - behavior_player
            executed_actions = {
                behavior_player: (
                    label_actions[behavior_player]
                    if behavior is None
                    or behavior_rng.random() < config.expert_probability
                    else behavior_actions[behavior_player]
                ),
                opponent_player: stationary_action(
                    env,
                    opponent_player,
                    prepared.action_masks[opponent_player],
                    rng=stationary_rng,
                    strategy_bot=stationary_bot,
                ),
            }
        with maybe_silence_stdio(config.quiet_engine):
            rewards, done, _ = env.step(
                executed_actions,
                pre_action_masks=prepared.action_masks,
            )
        previous_actions = [executed_actions[0], executed_actions[1]]
        previous_rewards = [float(rewards[0]), float(rewards[1])]
        episode_starts = [False, False]
        if done:
            episode_id += 1
            with maybe_silence_stdio(config.quiet_engine):
                env.reset(seed=config.seed + episode_id * 1009)
            previous_actions = [env.action_space.no_op_action] * 2
            previous_rewards = [0.0, 0.0]
            episode_starts = [True, True]
            if behavior is not None:
                behavior_states = [
                    behavior.model.initial_state(1, device=torch.device("cpu"))
                    for _ in range(2)
                ]

    return {name: np.asarray(values) for name, values in arrays.items()}  # type: ignore[arg-type]


def _collect_and_publish_oracle_shard(config: _CorpusShardConfig) -> str:
    if not reusable_shard(config.shard_path, config.shard_spec):
        publish_shard(
            config.shard_path,
            config.shard_spec,
            _collect_oracle_shard(config),
        )
    return str(config.shard_path)


def collect_oracle_corpus(
    *,
    output_path: Path,
    decks_path: Path,
    decisions: int,
    seed: int,
    decision_interval: int,
    max_ticks: int,
    planner_depth: int,
    planner_simulations: int,
    planner_action_samples: int,
    max_entities: int,
    quiet_engine: bool,
    reward_profile: str = DEFENSE_V2,
    workers: int = 1,
    behavior_checkpoint: Path | None = None,
    expert_probability: float = 1.0,
    stable_root_candidates: bool = False,
    behavior_opponent: str | None = None,
    label_source: str = "oracle",
    label_strategy: str | None = None,
    sampling_decks_path: Path | None = None,
) -> CorpusMetadata:
    if decisions <= 0:
        raise ValueError("decisions must be positive")
    if workers <= 0:
        raise ValueError("workers must be positive")
    if reward_profile not in REWARD_PROFILES:
        raise ValueError(f"unknown reward profile {reward_profile!r}")
    if not 0.0 <= expert_probability <= 1.0:
        raise ValueError("expert_probability must be between zero and one")
    if behavior_checkpoint is None and expert_probability != 1.0:
        raise ValueError("expert_probability below one requires a behavior checkpoint")
    if label_source not in LABEL_SOURCES:
        raise ValueError(f"unknown label source {label_source!r}")
    if label_source == "behavior" and behavior_checkpoint is None:
        raise ValueError("behavior labels require a behavior checkpoint")
    if label_source == "behavior" and expert_probability != 0.0:
        raise ValueError("behavior labels require expert_probability zero")
    if label_source == "strategy" and label_strategy is None:
        raise ValueError("strategy labels require a label strategy")
    if label_source != "strategy" and label_strategy is not None:
        raise ValueError("label strategy requires strategy labels")
    if label_strategy is not None and parse_stationary_opponent(label_strategy) is None:
        raise ValueError("label strategy must name a deterministic strategy bot")
    if behavior_opponent is not None:
        parse_stationary_opponent(behavior_opponent)
    worker_count = min(workers, decisions)
    base_decisions, remainder = divmod(decisions, worker_count)
    fingerprint = corpus_fingerprint(
        {
            "schema_version": CORPUS_SCHEMA_VERSION,
            "decks_sha256": file_sha256(decks_path),
            "sampling_decks_sha256": (
                file_sha256(sampling_decks_path)
                if sampling_decks_path is not None
                else None
            ),
            "decisions": decisions,
            "seed": seed,
            "decision_interval": decision_interval,
            "max_ticks": max_ticks,
            "planner_depth": planner_depth,
            "planner_simulations": planner_simulations,
            "planner_action_samples": planner_action_samples,
            "max_entities": max_entities,
            "reward_profile": reward_profile,
            "workers": worker_count,
            "behavior_checkpoint_sha256": (
                file_sha256(behavior_checkpoint)
                if behavior_checkpoint is not None
                else None
            ),
            "expert_probability": expert_probability,
            "stable_root_candidates": stable_root_candidates,
            "behavior_opponent": behavior_opponent,
            "label_source": label_source,
            "label_strategy": label_strategy,
            "stationary_label_scope": (
                "behavior-seat-only" if behavior_opponent is not None else None
            ),
            "behavior_seat_schedule": (
                "(shard_index+episode_id)%2" if behavior_opponent is not None else None
            ),
            "stationary_rng_offset": (
                STATIONARY_RNG_OFFSET if behavior_opponent is not None else None
            ),
        }
    )
    shards = [
        _CorpusShardConfig(
            decks_path=decks_path,
            sampling_decks_path=sampling_decks_path,
            decisions=base_decisions + int(shard_index < remainder),
            seed=seed + shard_index * 1_000_003,
            decision_interval=decision_interval,
            max_ticks=max_ticks,
            planner_depth=planner_depth,
            planner_simulations=planner_simulations,
            planner_action_samples=planner_action_samples,
            max_entities=max_entities,
            quiet_engine=quiet_engine,
            reward_profile=reward_profile,
            behavior_checkpoint=behavior_checkpoint,
            expert_probability=expert_probability,
            stable_root_candidates=stable_root_candidates,
            behavior_opponent=behavior_opponent,
            label_source=label_source,
            label_strategy=label_strategy,
            shard_spec=CorpusShardSpec(
                corpus_fingerprint=fingerprint,
                shard_index=shard_index,
                shard_count=worker_count,
                decisions=base_decisions + int(shard_index < remainder),
                seed=seed + shard_index * 1_000_003,
                samples_per_decision=(1 if behavior_opponent is not None else 2),
            ),
            shard_path=shard_path(output_path, shard_index, worker_count),
        )
        for shard_index in range(worker_count)
    ]
    completed = [
        shard.shard_spec.shard_index
        for shard in shards
        if reusable_shard(shard.shard_path, shard.shard_spec)
    ]
    publish_manifest(
        output_path,
        corpus_fingerprint=fingerprint,
        shard_count=worker_count,
        completed_shards=completed,
        complete=False,
    )
    if worker_count == 1:
        published_paths = [_collect_and_publish_oracle_shard(shards[0])]
    else:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            published_paths = list(
                executor.map(_collect_and_publish_oracle_shard, shards)
            )

    publish_manifest(
        output_path,
        corpus_fingerprint=fingerprint,
        shard_count=worker_count,
        completed_shards=list(range(worker_count)),
        complete=False,
    )
    shard_arrays = [
        load_shard(Path(published_path), shard.shard_spec)
        for published_path, shard in zip(published_paths, shards, strict=True)
    ]

    episode_offset = 0
    merged_chunks: dict[str, list[np.ndarray]] = {name: [] for name in shard_arrays[0]}
    for arrays in shard_arrays:
        episode_ids = arrays["episode_ids"].copy()
        episode_ids += episode_offset
        arrays["episode_ids"] = episode_ids
        episode_offset = int(episode_ids.max()) + 1
        for name, values in arrays.items():
            merged_chunks[name].append(values)
    merged = {
        name: np.concatenate(chunks, axis=0) for name, chunks in merged_chunks.items()
    }

    if behavior_checkpoint is None:
        builder = StructuredObservationBuilder(
            decks_path=decks_path,
            max_entities=max_entities,
        )
    else:
        behavior_state = torch.load(
            behavior_checkpoint,
            map_location="cpu",
            weights_only=False,
        )
        behavior_config = PolicyConfig.from_dict(behavior_state["model_config"])
        if behavior_config.max_entities != max_entities:
            raise ValueError("behavior checkpoint max_entities does not match corpus")
        builder = StructuredObservationBuilder(
            decks_path=decks_path,
            max_entities=max_entities,
            token_names=behavior_state["token_names"],
            card_semantics_version=behavior_config.card_semantics_version,
            canonical_lane_globals=behavior_config.canonical_lane_globals,
            public_history_slots=behavior_config.public_history_slots,
            public_seen_card_slots=behavior_config.public_seen_card_slots,
        )
    metadata = CorpusMetadata(
        schema_version=CORPUS_SCHEMA_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(),
        seed=seed,
        decisions=decisions,
        samples=decisions if behavior_opponent is not None else 2 * decisions,
        decision_interval=decision_interval,
        max_ticks=max_ticks,
        planner_depth=planner_depth,
        planner_simulations=planner_simulations,
        planner_action_samples=planner_action_samples,
        max_entities=max_entities,
        token_names=builder.token_names,
        reward_profile=reward_profile,
        workers=worker_count,
        behavior_checkpoint=(
            str(behavior_checkpoint) if behavior_checkpoint is not None else None
        ),
        expert_probability=expert_probability,
        stable_root_candidates=stable_root_candidates,
        behavior_opponent=behavior_opponent,
        label_source=label_source,
        label_strategy=label_strategy,
        sampling_decks_path=(
            str(sampling_decks_path) if sampling_decks_path is not None else None
        ),
    )
    atomic_save_npz(
        output_path,
        {
            **merged,
            "metadata_json": np.asarray(metadata.to_json()),
        },
    )
    publish_manifest(
        output_path,
        corpus_fingerprint=fingerprint,
        shard_count=worker_count,
        completed_shards=list(range(worker_count)),
        complete=True,
    )
    return metadata


def validate_corpus_levels(arrays: dict[str, np.ndarray], *, required: bool = False) -> None:
    """Keep old corpora unknown; reject partial or fabricated level records."""
    for scope, identity, mask in (("entity", "entity_ids", "entity_mask"), ("hand", "hand_ids", None)):
        names = (f"{scope}_levels", f"{scope}_level_confidence")
        present = [name in arrays for name in names]
        if not any(present) and not required:
            continue
        if not all(present):
            raise ValueError(f"missing {scope} level/confidence pair")
        levels, confidence = (arrays[name] for name in names)
        if levels.dtype != np.int64 or confidence.dtype != np.float32:
            raise ValueError(f"invalid {scope} level dtype")
        expected_shape = arrays[identity].shape if scope == "entity" else (*arrays[identity].shape[:-1], VISIBLE_CARD_SLOTS)
        if levels.shape != expected_shape or confidence.shape != levels.shape:
            raise ValueError(f"invalid {scope} level shape")
        if (not np.isfinite(confidence).all() or np.any((confidence < 0) | (confidence > 1))
            or np.any((levels < 0) | (levels > 127))
            or np.any((levels == 0) != (confidence == 0))):
            raise ValueError(f"invalid {scope} levels or confidence")
        if mask and np.any(levels[~arrays[mask]] != 0):
            raise ValueError("padded entity levels must be unknown")


def load_corpus(path: Path) -> tuple[CorpusMetadata, dict[str, np.ndarray]]:
    with np.load(path, allow_pickle=False) as payload:
        metadata = CorpusMetadata.from_json(str(payload["metadata_json"].item()))
        if metadata.schema_version != CORPUS_SCHEMA_VERSION:
            raise ValueError(f"unsupported corpus schema {metadata.schema_version}")
        arrays = {
            name: payload[name].copy()
            for name in (
                "entity_ids",
                "entity_features",
                "entity_mask",
                "hand_ids",
                "global_features",
                "action_masks",
                "previous_actions",
                "previous_rewards",
                "episode_starts",
                "expert_actions",
                "episode_ids",
            )
        }
        for optional_name in (
            "board_rotated",
            "terminal_status",
            "entity_levels",
            "entity_level_confidence",
            "hand_levels",
            "hand_level_confidence",
            "opponent_history_ids",
            "opponent_history_ages",
            "opponent_seen_card_ids",
            "own_last_play_ids",
            "own_last_play_features",
            "entity_id_confidence",
            "entity_feature_confidence",
            "hand_id_confidence",
            "global_feature_confidence",
            "expert_action_supervision_valid",
            "source_frames",
            "source_replays",
            "source_family_ids",
            "fit_split",
            "source_actor_ids",
            "source_snapshots",
        ):
            if optional_name in payload:
                arrays[optional_name] = payload[optional_name].copy()
    validate_corpus_levels(arrays, required=metadata.public_contract_version >= 4)
    if arrays["expert_actions"].shape[0] != metadata.samples:
        raise ValueError("corpus sample count does not match metadata")
    legal = arrays["action_masks"][
        np.arange(metadata.samples), arrays["expert_actions"]
    ]
    supervision_valid = arrays.get("expert_action_supervision_valid")
    if supervision_valid is None:
        supervision_valid = np.ones((metadata.samples,), dtype=np.bool_)
    else:
        supervision_valid = np.asarray(supervision_valid, dtype=np.bool_)
        if supervision_valid.shape != (metadata.samples,):
            raise ValueError(
                "corpus expert-action supervision validity shape mismatch"
            )
        arrays["expert_action_supervision_valid"] = supervision_valid
    if np.any(supervision_valid & ~legal):
        raise ValueError("corpus contains a supervised illegal expert action")
    if metadata.public_contract_version >= 4:
        from .public_policy_contract import ARRAY_DTYPES, CONFIDENCE_FIELDS, ALL_LEVEL_DTYPES, PublicPolicySequence
        names = set(ARRAY_DTYPES) | set(CONFIDENCE_FIELDS) | set(ALL_LEVEL_DTYPES)
        if missing := names - arrays.keys():
            raise ValueError(f"public-v4 corpus fields missing: {sorted(missing)}")
        public = PublicPolicySequence(metadata.token_names, {name: arrays[name] for name in names if name in arrays})
        public.validate_action_mask(arrays["action_masks"])
        if np.any(arrays["previous_rewards"] != 0):
            raise ValueError("public-v4 corpus must not expose previous rewards")
    return metadata, arrays


def load_public_observation_sidecar(
    path: Path,
    *,
    base_arrays: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """Overlay aligned noisy public observations without mutating a v1 corpus."""

    with np.load(path, allow_pickle=False) as payload:
        if "schema_version" not in payload:
            raise ValueError("public observation sidecar has no schema version")
        schema_version = int(payload["schema_version"].item())
        if schema_version != PUBLIC_OBSERVATION_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported public observation schema {schema_version}"
            )
        if "feature_contract_version" in payload:
            feature_contract_version = int(
                payload["feature_contract_version"].item()
            )
            if feature_contract_version != REAL_PLAY_FEATURE_CONTRACT_VERSION:
                raise ValueError(
                    "unsupported real-play feature contract "
                    f"{feature_contract_version}"
                )
        if "action_mask_contract_version" not in payload:
            raise ValueError(
                "public observation sidecar has no label-independent action-mask contract"
            )
        action_mask_contract_version = int(
            payload["action_mask_contract_version"].item()
        )
        if action_mask_contract_version != PUBLIC_ACTION_MASK_CONTRACT_VERSION:
            raise ValueError(
                "unsupported public action-mask contract "
                f"{action_mask_contract_version}"
            )
        required = (
            "entity_ids",
            "entity_features",
            "entity_mask",
            "entity_id_confidence",
            "entity_feature_confidence",
            "hand_ids",
            "hand_id_confidence",
            "global_features",
            "global_feature_confidence",
            "action_masks",
            "expert_action_masked",
        )
        missing = [name for name in required if name not in payload]
        if missing:
            raise ValueError(f"public observation sidecar is missing arrays: {missing}")
        sidecar = {name: payload[name].copy() for name in required}
        for name in ("entity_levels", "entity_level_confidence", "hand_levels", "hand_level_confidence"):
            if name in payload:
                sidecar[name] = payload[name].copy()
        validate_corpus_levels(sidecar)
        for alignment_name in ("expert_actions", "episode_ids", "source_frames"):
            if (
                alignment_name in payload
                and alignment_name in base_arrays
                and not np.array_equal(
                    payload[alignment_name], base_arrays[alignment_name]
                )
            ):
                raise ValueError(
                    f"public observation sidecar {alignment_name} is not aligned"
                )
    samples = int(base_arrays["expert_actions"].shape[0])
    for name, values in sidecar.items():
        if values.shape[0] != samples:
            raise ValueError(
                f"public observation sidecar {name} has {values.shape[0]} rows, "
                f"expected {samples}"
            )
    for name in ("entity_ids", "entity_features", "entity_mask"):
        if sidecar[name].shape != base_arrays[name].shape:
            raise ValueError(f"public observation sidecar {name} shape mismatch")
    if sidecar["hand_ids"].shape != base_arrays["hand_ids"].shape:
        raise ValueError("public observation sidecar hand_ids shape mismatch")
    if sidecar["hand_ids"].shape[-1] > VISIBLE_CARD_SLOTS and (
        np.any(sidecar["hand_ids"][..., VISIBLE_CARD_SLOTS:] != 0)
        or np.any(
            sidecar["hand_id_confidence"][..., VISIBLE_CARD_SLOTS:] > 0.0
        )
    ):
        raise ValueError(
            "public observation sidecar exposes hidden future hand cards"
        )
    if sidecar["global_features"].shape != base_arrays["global_features"].shape:
        raise ValueError("public observation sidecar global_features shape mismatch")
    if sidecar["action_masks"].shape != base_arrays["action_masks"].shape:
        raise ValueError("public observation sidecar action_masks shape mismatch")
    sidecar["action_masks"] = sidecar["action_masks"].astype(
        np.bool_, copy=False
    )
    expert_actions = base_arrays["expert_actions"].astype(
        np.int64, copy=False
    )
    expert_action_masked = np.asarray(
        sidecar["expert_action_masked"], dtype=np.bool_
    )
    if expert_action_masked.shape != expert_actions.shape:
        raise ValueError(
            "public observation sidecar expert_action_masked shape mismatch"
        )
    actual_expert_action_masked = ~sidecar["action_masks"][
        np.arange(expert_actions.size), expert_actions
    ]
    if not np.array_equal(expert_action_masked, actual_expert_action_masked):
        raise ValueError(
            "public observation sidecar expert_action_masked is inconsistent"
        )
    expected_confidence_shapes = {
        "entity_id_confidence": sidecar["entity_ids"].shape,
        "entity_feature_confidence": sidecar["entity_features"].shape,
        "hand_id_confidence": sidecar["hand_ids"].shape,
        "global_feature_confidence": sidecar["global_features"].shape,
    }
    for name, expected_shape in expected_confidence_shapes.items():
        values = sidecar[name]
        if values.shape != expected_shape:
            raise ValueError(f"public observation sidecar {name} shape mismatch")
        if not np.isfinite(values).all() or np.any((values < 0.0) | (values > 1.0)):
            raise ValueError(f"public observation sidecar {name} must be finite in [0, 1]")
    value_confidence_pairs = (
        ("entity_ids", "entity_id_confidence"),
        ("entity_features", "entity_feature_confidence"),
        ("hand_ids", "hand_id_confidence"),
        ("global_features", "global_feature_confidence"),
    )
    for value_name, confidence_name in value_confidence_pairs:
        values = sidecar[value_name]
        confidence = sidecar[confidence_name]
        if np.any(values[confidence <= 0.0] != 0):
            raise ValueError(
                f"public observation sidecar {value_name} fabricates "
                "values where confidence is zero"
            )
    leaked_entities = [
        ENTITY_FEATURE_NAMES[index]
        for index in range(sidecar["entity_features"].shape[-1])
        if index not in REAL_PLAY_ENTITY_FEATURE_INDICES
        and np.any(sidecar["entity_feature_confidence"][..., index] > 0.0)
    ]
    leaked_globals = [
        GLOBAL_FEATURE_NAMES[index]
        for index in range(sidecar["global_features"].shape[-1])
        if index not in REAL_PLAY_GLOBAL_FEATURE_INDICES
        and np.any(sidecar["global_feature_confidence"][..., index] > 0.0)
    ]
    if leaked_entities or leaked_globals:
        raise ValueError(
            "public observation sidecar exceeds real-play feature contract: "
            f"entity={leaked_entities}, global={leaked_globals}"
        )
    merged = dict(base_arrays)
    for name in ("entity_levels", "entity_level_confidence", "hand_levels", "hand_level_confidence"):
        merged.pop(name, None)
    merged.update(sidecar)
    # Keep masked demonstrations as recurrent context, but never train their
    # target through a policy mask that says the action was unavailable.
    source_supervision_valid = np.asarray(
        base_arrays.get(
            "expert_action_supervision_valid",
            np.ones_like(expert_action_masked, dtype=np.bool_),
        ),
        dtype=np.bool_,
    )
    if source_supervision_valid.shape != expert_action_masked.shape:
        raise ValueError("base expert-action supervision validity shape mismatch")
    merged["expert_action_supervision_valid"] = (
        source_supervision_valid & ~expert_action_masked
    )
    # The simulator's shaped reward is training supervision, not a screen
    # observation. A causal recurrent actor must infer consequences from the
    # next visual state instead of receiving this privileged scalar.
    merged["previous_rewards"] = np.zeros_like(
        base_arrays["previous_rewards"], dtype=np.float32
    )
    return merged


def load_policy_state_with_confidence_upgrade(
    model: ClasherPolicy,
    state_dict: dict[str, torch.Tensor],
    *,
    upgrade_legacy_confidence: bool,
) -> None:
    if not upgrade_legacy_confidence:
        model.load_state_dict(state_dict)
        return
    incompatible = model.load_state_dict(state_dict, strict=False)
    if incompatible.unexpected_keys or set(incompatible.missing_keys) != set(
        PUBLIC_CONFIDENCE_STATE_KEYS
    ):
        raise ValueError(
            "legacy confidence upgrade found unexpected checkpoint differences: "
            f"missing={incompatible.missing_keys}, "
            f"unexpected={incompatible.unexpected_keys}"
        )


def split_indices(
    episode_ids: np.ndarray,
    *,
    validation_fraction: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be between zero and one")
    count = int(episode_ids.shape[0])
    if count < 2:
        raise ValueError("corpus needs at least two samples")
    rng = np.random.default_rng(seed)
    unique_episodes = np.unique(episode_ids)
    if unique_episodes.size >= 2:
        shuffled = rng.permutation(unique_episodes)
        validation_episodes = set(
            shuffled[
                : max(1, round(unique_episodes.size * validation_fraction))
            ].tolist()
        )
        validation = np.asarray(
            [
                index
                for index, episode in enumerate(episode_ids)
                if episode in validation_episodes
            ],
            dtype=np.int64,
        )
        training = np.asarray(
            [
                index
                for index, episode in enumerate(episode_ids)
                if episode not in validation_episodes
            ],
            dtype=np.int64,
        )
        if training.size and validation.size:
            return training, validation
    permutation = rng.permutation(count)
    validation_count = max(1, min(count - 1, round(count * validation_fraction)))
    return permutation[validation_count:], permutation[:validation_count]


def informative_indices(action_masks: np.ndarray) -> np.ndarray:
    """Return rows whose masked policy has a non-trivial action choice."""
    if action_masks.ndim != 2:
        raise ValueError("action masks must have shape [samples, actions]")
    return np.flatnonzero(np.count_nonzero(action_masks, axis=1) > 1).astype(
        np.int64,
        copy=False,
    )


def imitation_supervision_mask(
    action_masks: np.ndarray,
    expert_actions: np.ndarray,
    *,
    train_on_forced_actions: bool,
    placement_actions_only: bool,
) -> np.ndarray:
    """Return rows that contribute supervised loss while sequences still advance."""
    if action_masks.ndim != 2 or expert_actions.shape != action_masks.shape[:1]:
        raise ValueError("imitation action arrays have incompatible shapes")
    selected = (
        np.ones(expert_actions.shape[0], dtype=np.bool_)
        if train_on_forced_actions
        else np.count_nonzero(action_masks, axis=1) > 1
    )
    if placement_actions_only:
        selected &= expert_actions < PLACEMENT_ACTIONS
    return selected


def expert_card_balance_weights(
    hand_ids: np.ndarray,
    expert_actions: np.ndarray,
    reference_indices: np.ndarray,
    *,
    power: float,
    max_weight: float,
) -> np.ndarray:
    """Build clipped inverse-frequency weights for expert-played cards.

    Wait and ability decisions retain weight one. Card frequencies come only
    from the training partition. Placement weights are normalized to mean one
    on that partition, preserving the overall loss scale while preventing
    frequent cycle cards from drowning out less common strategic roles.
    """

    if not 0.0 <= power <= 1.0:
        raise ValueError("expert card balance power must be between zero and one")
    if max_weight < 1.0:
        raise ValueError("maximum expert card weight must be at least one")
    if hand_ids.ndim != 2 or hand_ids.shape[1] < NUM_HAND_SLOTS:
        raise ValueError("hand IDs must have at least four slots")
    if expert_actions.shape != hand_ids.shape[:1]:
        raise ValueError("expert actions must align with hand IDs")

    weights = np.ones(expert_actions.shape, dtype=np.float32)
    if power == 0.0:
        return weights
    reference = np.asarray(reference_indices, dtype=np.int64)
    reference_actions = expert_actions[reference]
    reference_placements = reference_actions < PLACEMENT_ACTIONS
    placement_reference = reference[reference_placements]
    if placement_reference.size == 0:
        return weights
    reference_slots = reference_actions[reference_placements] // NUM_TILES
    reference_cards = hand_ids[placement_reference, reference_slots]
    counts = np.bincount(reference_cards, minlength=int(hand_ids.max()) + 1)

    placements = expert_actions < PLACEMENT_ACTIONS
    placement_rows = np.flatnonzero(placements)
    placement_slots = expert_actions[placements] // NUM_TILES
    placement_cards = hand_ids[placement_rows, placement_slots]
    frequencies = np.maximum(1, counts[placement_cards]).astype(np.float64)
    raw = np.power(frequencies, -power)
    reference_raw = np.power(
        np.maximum(1, counts[reference_cards]).astype(np.float64), -power
    )
    lower = 0.0
    epsilon = float(np.finfo(np.float64).eps)
    upper = 1.0 / max(float(reference_raw.mean()), epsilon)
    while float(np.minimum(reference_raw * upper, max_weight).mean()) < 1.0:
        upper *= 2.0
    for _ in range(48):
        scale = (lower + upper) * 0.5
        if float(np.minimum(reference_raw * scale, max_weight).mean()) < 1.0:
            lower = scale
        else:
            upper = scale
    weights[placement_rows] = np.minimum(raw * upper, max_weight).astype(np.float32)
    return weights


def defensive_context_weights(
    entity_features: np.ndarray,
    entity_mask: np.ndarray,
    *,
    context_weight: float,
    maximum_canonical_y: float,
) -> np.ndarray:
    """Upweight human decisions made under visible incoming pressure.

    The context is public and card-agnostic: at least one detected enemy troop
    or building must be on the observed player's defended side.  All rows stay
    in the corpus, so this is a rehearsal-preserving emphasis rather than a
    defense-only dataset that could erase ordinary offense and cycling.
    """

    if context_weight < 1.0:
        raise ValueError("defensive context weight must be at least one")
    selected = visible_enemy_pressure_mask(
        entity_features,
        entity_mask,
        maximum_canonical_y=maximum_canonical_y,
    )
    weights = np.ones(selected.shape, dtype=np.float32)
    weights[selected] = float(context_weight)
    return weights


def expert_action_type_balance_weights(
    expert_actions: np.ndarray,
    reference_indices: np.ndarray,
    *,
    power: float,
    max_weight: float,
) -> np.ndarray:
    """Balance four card slots, wait, and ability from training rows only."""

    if not 0.0 <= power <= 1.0:
        raise ValueError("expert action type balance power must be between zero and one")
    if max_weight < 1.0:
        raise ValueError("maximum expert action type weight must be at least one")
    actions = np.asarray(expert_actions, dtype=np.int64)
    action_types = np.where(
        actions < PLACEMENT_ACTIONS,
        actions // NUM_TILES,
        NUM_HAND_SLOTS + (actions > PLACEMENT_ACTIONS).astype(np.int64),
    )
    weights = np.ones(actions.shape, dtype=np.float32)
    if power == 0.0:
        return weights
    reference = np.asarray(reference_indices, dtype=np.int64)
    counts = np.bincount(action_types[reference], minlength=NUM_HAND_SLOTS + 2)
    frequencies = np.maximum(1, counts[action_types]).astype(np.float64)
    reference_raw = np.power(
        np.maximum(1, counts[action_types[reference]]).astype(np.float64), -power
    )
    raw = np.power(frequencies, -power)
    lower = 0.0
    upper = 1.0 / max(float(reference_raw.mean()), float(np.finfo(np.float64).eps))
    while float(np.minimum(reference_raw * upper, max_weight).mean()) < 1.0:
        upper *= 2.0
    for _ in range(48):
        scale = 0.5 * (lower + upper)
        if float(np.minimum(reference_raw * scale, max_weight).mean()) < 1.0:
            lower = scale
        else:
            upper = scale
    weights[:] = np.minimum(raw * upper, max_weight).astype(np.float32)
    return weights


def expert_decision_balance_weights(
    expert_actions: np.ndarray,
    reference_indices: np.ndarray,
    *,
    power: float,
    max_weight: float,
) -> np.ndarray:
    """Balance play, wait, and ability for a hierarchical decision gate."""

    actions = np.asarray(expert_actions, dtype=np.int64)
    decisions = np.where(
        actions < PLACEMENT_ACTIONS,
        0,
        1 + (actions > PLACEMENT_ACTIONS).astype(np.int64),
    )
    # Reuse the exact bounded normalization by encoding the three decisions as
    # representative flat action IDs for play-slot-zero, wait, and ability.
    representative = np.where(
        decisions == 0,
        0,
        PLACEMENT_ACTIONS + (decisions - 1),
    )
    return expert_action_type_balance_weights(
        representative,
        reference_indices,
        power=power,
        max_weight=max_weight,
    )


def _batch_inputs(
    arrays: dict[str, np.ndarray],
    indices: np.ndarray,
    device: torch.device,
    *,
    trim_entity_padding: bool = False,
) -> PolicyInputs:
    def tensor(name: str, dtype: torch.dtype) -> torch.Tensor:
        return torch.as_tensor(
            arrays[name][indices], dtype=dtype, device=device
        ).unsqueeze(1)

    def optional_tensor(name: str, dtype: torch.dtype) -> torch.Tensor | None:
        return tensor(name, dtype) if name in arrays else None

    if trim_entity_padding:
        selected_mask = arrays["entity_mask"][indices]
        entity_width = _packed_entity_width_numpy(selected_mask)
        entity_ids = torch.as_tensor(
            arrays["entity_ids"][indices, :entity_width],
            dtype=torch.long,
            device=device,
        ).unsqueeze(1)
        entity_features = torch.as_tensor(
            arrays["entity_features"][indices, :entity_width, :],
            dtype=torch.float32,
            device=device,
        ).unsqueeze(1)
        entity_mask = torch.as_tensor(
            selected_mask[..., :entity_width], dtype=torch.bool, device=device
        ).unsqueeze(1)
        entity_id_confidence = (
            torch.as_tensor(
                arrays["entity_id_confidence"][indices, :entity_width],
                dtype=torch.float32,
                device=device,
            ).unsqueeze(1)
            if "entity_id_confidence" in arrays
            else None
        )
        entity_feature_confidence = (
            torch.as_tensor(
                arrays["entity_feature_confidence"][indices, :entity_width, :],
                dtype=torch.float32,
                device=device,
            ).unsqueeze(1)
            if "entity_feature_confidence" in arrays
            else None
        )
    else:
        entity_ids = tensor("entity_ids", torch.long)
        entity_features = tensor("entity_features", torch.float32)
        entity_mask = tensor("entity_mask", torch.bool)
        entity_id_confidence = optional_tensor(
            "entity_id_confidence", torch.float32
        )
        entity_feature_confidence = optional_tensor(
            "entity_feature_confidence", torch.float32
        )
    entity_levels = optional_tensor("entity_levels", torch.long)
    entity_level_confidence = optional_tensor("entity_level_confidence", torch.float32)
    if trim_entity_padding:
        if entity_levels is not None:
            entity_levels = entity_levels[..., :entity_ids.shape[-1]]
        if entity_level_confidence is not None:
            entity_level_confidence = entity_level_confidence[..., :entity_ids.shape[-1]]
    return PolicyInputs(
        entity_levels=entity_levels,
        entity_level_confidence=entity_level_confidence,
        hand_levels=optional_tensor("hand_levels", torch.long),
        hand_level_confidence=optional_tensor("hand_level_confidence", torch.float32),
        opponent_history_ids=optional_tensor("opponent_history_ids", torch.long),
        opponent_history_ages=optional_tensor("opponent_history_ages", torch.float32),
        opponent_seen_card_ids=optional_tensor("opponent_seen_card_ids", torch.long),
        own_last_play_ids=optional_tensor("own_last_play_ids", torch.long),
        own_last_play_features=optional_tensor("own_last_play_features", torch.float32),
        entity_ids=entity_ids,
        entity_features=entity_features,
        entity_mask=entity_mask,
        hand_ids=tensor("hand_ids", torch.long),
        global_features=tensor("global_features", torch.float32),
        action_mask=tensor("action_masks", torch.bool),
        previous_actions=tensor("previous_actions", torch.long),
        previous_rewards=tensor("previous_rewards", torch.float32),
        # Single-example batches deliberately reset memory. This trains the
        # exact V2 actor architecture without smuggling privileged sequence
        # state into a shuffled demonstration baseline.
        episode_starts=torch.ones((len(indices), 1), dtype=torch.bool, device=device),
        entity_id_confidence=entity_id_confidence,
        entity_feature_confidence=entity_feature_confidence,
        hand_id_confidence=optional_tensor("hand_id_confidence", torch.float32),
        global_feature_confidence=optional_tensor(
            "global_feature_confidence", torch.float32
        ),
    )


def sequence_chunks(
    episode_ids: np.ndarray,
    indices: np.ndarray,
    *,
    sequence_length: int,
    preserve_tails: bool = False,
) -> np.ndarray:
    """Return episode chunks; public terminal context can pad a final short tail."""

    if sequence_length <= 1:
        raise ValueError("sequence_length must be greater than one")
    allowed = np.zeros(len(episode_ids), dtype=np.bool_)
    allowed[indices] = True
    chunks: list[np.ndarray] = []
    for episode_id in np.unique(episode_ids[indices]):
        episode_indices = np.flatnonzero((episode_ids == episode_id) & allowed)
        if episode_indices.size < sequence_length and not preserve_tails:
            continue
        if np.any(np.diff(episode_indices) != 1):
            raise ValueError("episode samples must be contiguous")
        usable = episode_indices.size - episode_indices.size % sequence_length
        if preserve_tails and usable < episode_indices.size:
            tail = episode_indices[usable:]
            chunks.append(np.pad(tail, (0, sequence_length - len(tail)), constant_values=tail[-1]))
        chunks.extend(
            episode_indices[start : start + sequence_length]
            for start in range(0, usable, sequence_length)
        )
    if not chunks:
        raise ValueError("corpus has no complete imitation sequences")
    return np.stack(chunks)


def _packed_entity_width_numpy(selected_mask: np.ndarray) -> int:
    if np.any(selected_mask[..., 1:] & ~selected_mask[..., :-1]):
        raise ValueError("entity masks must pack valid rows before padding")
    return max(1, int(np.count_nonzero(selected_mask, axis=-1).max()))


def _sequence_batch_inputs(
    arrays: dict[str, np.ndarray],
    chunk_indices: np.ndarray,
    device: torch.device,
    *,
    trim_entity_padding: bool = False,
    reset_memory: bool = True,
) -> PolicyInputs:
    def tensor(name: str, dtype: torch.dtype) -> torch.Tensor:
        return torch.as_tensor(arrays[name][chunk_indices], dtype=dtype, device=device)

    def optional_tensor(name: str, dtype: torch.dtype) -> torch.Tensor | None:
        return tensor(name, dtype) if name in arrays else None

    episode_starts = tensor("episode_starts", torch.bool).clone()
    # Truncated chunks do not carry hidden state across optimizer batches.
    if reset_memory:
        episode_starts[:, 0] = True
    if trim_entity_padding:
        selected_mask = arrays["entity_mask"][chunk_indices]
        entity_width = _packed_entity_width_numpy(selected_mask)
        entity_ids = torch.as_tensor(
            arrays["entity_ids"][chunk_indices, :entity_width],
            dtype=torch.long,
            device=device,
        )
        entity_features = torch.as_tensor(
            arrays["entity_features"][chunk_indices, :entity_width, :],
            dtype=torch.float32,
            device=device,
        )
        entity_mask = torch.as_tensor(
            selected_mask[..., :entity_width], dtype=torch.bool, device=device
        )
        entity_id_confidence = (
            torch.as_tensor(
                arrays["entity_id_confidence"][chunk_indices, :entity_width],
                dtype=torch.float32,
                device=device,
            )
            if "entity_id_confidence" in arrays
            else None
        )
        entity_feature_confidence = (
            torch.as_tensor(
                arrays["entity_feature_confidence"][
                    chunk_indices, :entity_width, :
                ],
                dtype=torch.float32,
                device=device,
            )
            if "entity_feature_confidence" in arrays
            else None
        )
    else:
        entity_ids = tensor("entity_ids", torch.long)
        entity_features = tensor("entity_features", torch.float32)
        entity_mask = tensor("entity_mask", torch.bool)
        entity_id_confidence = optional_tensor(
            "entity_id_confidence", torch.float32
        )
        entity_feature_confidence = optional_tensor(
            "entity_feature_confidence", torch.float32
        )
    entity_levels = optional_tensor("entity_levels", torch.long)
    entity_level_confidence = optional_tensor("entity_level_confidence", torch.float32)
    if trim_entity_padding:
        if entity_levels is not None:
            entity_levels = entity_levels[..., :entity_ids.shape[-1]]
        if entity_level_confidence is not None:
            entity_level_confidence = entity_level_confidence[..., :entity_ids.shape[-1]]
    return PolicyInputs(
        entity_levels=entity_levels,
        entity_level_confidence=entity_level_confidence,
        hand_levels=optional_tensor("hand_levels", torch.long),
        hand_level_confidence=optional_tensor("hand_level_confidence", torch.float32),
        opponent_history_ids=optional_tensor("opponent_history_ids", torch.long),
        opponent_history_ages=optional_tensor("opponent_history_ages", torch.float32),
        opponent_seen_card_ids=optional_tensor("opponent_seen_card_ids", torch.long),
        own_last_play_ids=optional_tensor("own_last_play_ids", torch.long),
        own_last_play_features=optional_tensor("own_last_play_features", torch.float32),
        entity_ids=entity_ids,
        entity_features=entity_features,
        entity_mask=entity_mask,
        hand_ids=tensor("hand_ids", torch.long),
        global_features=tensor("global_features", torch.float32),
        action_mask=tensor("action_masks", torch.bool),
        previous_actions=tensor("previous_actions", torch.long),
        previous_rewards=tensor("previous_rewards", torch.float32),
        episode_starts=episode_starts,
        entity_id_confidence=entity_id_confidence,
        entity_feature_confidence=entity_feature_confidence,
        hand_id_confidence=optional_tensor("hand_id_confidence", torch.float32),
        global_feature_confidence=optional_tensor(
            "global_feature_confidence", torch.float32
        ),
    )


def _council_imitation_state(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    chunk_indices: np.ndarray,
    *,
    device: torch.device,
    episode_offsets: dict[int, int],
) -> tuple[torch.Tensor, torch.Tensor]:
    from .council_recurrence import reconstruct_recurrent_state

    prefixes = []
    for chunk in chunk_indices:
        first = int(chunk[0])
        episode = int(arrays["episode_ids"][first])
        begin = episode_offsets[episode]
        prefixes.append(None if begin == first else _sequence_batch_inputs(
            arrays, np.arange(begin, first)[None, :], torch.device("cpu"),
            trim_entity_padding=True, reset_memory=False,
        ))
    return reconstruct_recurrent_state(model, tuple(prefixes), device=device)


def _imitation_evaluation_batches(model, arrays, indices, *, batch_size, device, trim_entity_padding):
    """Evaluate v4 in episode order, including unsupervised recurrent context."""
    if model.config.public_contract_version < 4:
        for start in range(0, len(indices), batch_size):
            selected = indices[start:start + batch_size]
            inputs = _batch_inputs(arrays, selected, device, trim_entity_padding=trim_entity_padding)
            yield selected, inputs, model(inputs)
        return
    allowed = np.zeros(len(arrays["episode_ids"]), dtype=bool)
    allowed[indices] = True
    for episode in np.unique(arrays["episode_ids"][indices]):
        rows = np.flatnonzero(arrays["episode_ids"] == episode)
        if np.any(np.diff(rows) != 1) or not arrays["episode_starts"][rows[0]]:
            raise ValueError("council evaluation requires complete contiguous episodes")
        state = model.initial_state(1, device=device)
        for begin in range(0, len(rows), min(batch_size, 128)):
            chunk = rows[begin:begin + min(batch_size, 128)]
            inputs = _sequence_batch_inputs(arrays, chunk[None, :], device,
                trim_entity_padding=trim_entity_padding, reset_memory=False)
            output = model(inputs, state)
            state = output.next_state
            chosen = np.flatnonzero(allowed[chunk])
            if len(chosen):
                selected = chunk[chosen]
                # Metrics use single-step batch shapes; inference above retained
                # the entire causal prefix and current chunk's real recurrence.
                metric_inputs = _batch_inputs(arrays, selected, device, trim_entity_padding=trim_entity_padding)
                metric_output = SimpleNamespace(**{name: getattr(output, name)[0, chosen].unsqueeze(1)
                    for name in ("joint_logits", "action_type_logits", "location_logits")})
                yield selected, metric_inputs, metric_output


def mirror_imitation_batch(
    inputs: PolicyInputs,
    targets: torch.Tensor,
    flip_rows: torch.Tensor,
) -> tuple[PolicyInputs, torch.Tensor]:
    """Mirror selected imitation sequences across the arena's vertical axis."""

    if flip_rows.ndim != 1 or flip_rows.shape[0] != inputs.batch_size:
        raise ValueError("flip_rows must have one boolean per batch row")
    flip_rows = flip_rows.to(device=inputs.entity_features.device, dtype=torch.bool)
    if not bool(flip_rows.any()):
        return inputs, targets

    def mirror_actions(actions: torch.Tensor) -> torch.Tensor:
        placement = actions < NUM_HAND_SLOTS * NUM_TILES
        slot = torch.div(actions, NUM_TILES, rounding_mode="floor")
        tile = actions.remainder(NUM_TILES)
        y = torch.div(tile, BOARD_WIDTH, rounding_mode="floor")
        x = tile.remainder(BOARD_WIDTH)
        mirrored = slot * NUM_TILES + y * BOARD_WIDTH + (BOARD_WIDTH - 1 - x)
        return torch.where(placement, mirrored, actions)

    entity_features = inputs.entity_features.clone()
    selected_entities = flip_rows[:, None, None] & inputs.entity_mask
    entity_features[..., 0] = torch.where(
        selected_entities,
        1.0 - entity_features[..., 0],
        entity_features[..., 0],
    )

    action_mask = inputs.action_mask.clone()
    selected_masks = action_mask[flip_rows]
    placement_masks = selected_masks[..., : NUM_HAND_SLOTS * NUM_TILES]
    placement_masks = placement_masks.reshape(
        *placement_masks.shape[:-1], NUM_HAND_SLOTS, BOARD_HEIGHT, BOARD_WIDTH
    ).flip(-1)
    action_mask[flip_rows] = torch.cat(
        [
            placement_masks.reshape(
                *placement_masks.shape[:-3], NUM_HAND_SLOTS * NUM_TILES
            ),
            selected_masks[..., NUM_HAND_SLOTS * NUM_TILES :],
        ],
        dim=-1,
    )

    previous_actions = inputs.previous_actions.clone()
    previous_actions[flip_rows] = mirror_actions(previous_actions[flip_rows])
    mirrored_targets = targets.clone()
    mirrored_targets[flip_rows] = mirror_actions(mirrored_targets[flip_rows])
    return (
        replace(
            inputs,
            entity_features=entity_features,
            action_mask=action_mask,
            previous_actions=previous_actions,
        ),
        mirrored_targets,
    )


def permute_hand_imitation_batch(
    inputs: PolicyInputs,
    targets: torch.Tensor,
    orders: torch.Tensor,
) -> tuple[PolicyInputs, torch.Tensor]:
    """Relabel the four current-hand slots consistently across each sequence.

    ``orders[b, new_slot]`` is the original slot moved into ``new_slot`` for
    every time step in batch row ``b``. Masks, actions, confidence, and the
    privileged own hand follow the same relabeling, so this is an exact
    observation/action symmetry rather than a changed battle trajectory.
    """

    if orders.shape != (inputs.batch_size, NUM_HAND_SLOTS):
        raise ValueError("orders must have shape [batch, four hand slots]")
    orders = orders.to(device=inputs.hand_ids.device, dtype=torch.long)
    expected = list(range(NUM_HAND_SLOTS))
    if any(sorted(row.tolist()) != expected for row in orders.cpu()):
        raise ValueError("each order row must be a four-slot permutation")

    batch_size, sequence_length = inputs.hand_ids.shape[:2]
    hand_indices = orders[:, None, :].expand(
        batch_size, sequence_length, NUM_HAND_SLOTS
    )

    hand_ids = inputs.hand_ids.clone()
    hand_ids[..., :NUM_HAND_SLOTS] = inputs.hand_ids[
        ..., :NUM_HAND_SLOTS
    ].gather(-1, hand_indices)

    hand_id_confidence = inputs.hand_id_confidence
    if hand_id_confidence is not None:
        original_hand_confidence = hand_id_confidence
        hand_id_confidence = hand_id_confidence.clone()
        hand_id_confidence[..., :NUM_HAND_SLOTS] = original_hand_confidence[
            ..., :NUM_HAND_SLOTS
        ].gather(-1, hand_indices)

    def permute_levels(values: torch.Tensor | None) -> torch.Tensor | None:
        if values is None:
            return None
        result = values.clone()
        result[..., :NUM_HAND_SLOTS] = values[..., :NUM_HAND_SLOTS].gather(-1, hand_indices)
        return result

    hand_levels = permute_levels(inputs.hand_levels)
    hand_level_confidence = permute_levels(inputs.hand_level_confidence)
    action_mask = inputs.action_mask.clone()
    placement_mask = inputs.action_mask[..., :PLACEMENT_ACTIONS].reshape(
        batch_size, sequence_length, NUM_HAND_SLOTS, NUM_TILES
    )
    placement_indices = orders[:, None, :, None].expand(
        batch_size, sequence_length, NUM_HAND_SLOTS, NUM_TILES
    )
    action_mask[..., :PLACEMENT_ACTIONS] = placement_mask.gather(
        2, placement_indices
    ).reshape(batch_size, sequence_length, PLACEMENT_ACTIONS)

    critic_card_ids = inputs.critic_card_ids
    if critic_card_ids is not None:
        original_critic_card_ids = critic_card_ids
        critic_card_ids = critic_card_ids.clone()
        critic_card_ids[..., :NUM_HAND_SLOTS] = original_critic_card_ids[
            ..., :NUM_HAND_SLOTS
        ].gather(-1, hand_indices)

    inverse_orders = torch.empty_like(orders)
    inverse_orders.scatter_(
        1,
        orders,
        torch.arange(NUM_HAND_SLOTS, device=orders.device)[None, :].expand_as(
            orders
        ),
    )

    def remap_actions(actions: torch.Tensor) -> torch.Tensor:
        if actions.shape[0] != batch_size:
            raise ValueError("actions must have the same batch dimension as inputs")
        placement = actions < PLACEMENT_ACTIONS
        old_slots = torch.div(
            actions.clamp(max=PLACEMENT_ACTIONS - 1),
            NUM_TILES,
            rounding_mode="floor",
        )
        expanded_inverse = inverse_orders.reshape(
            batch_size,
            *((1,) * (actions.ndim - 1)),
            NUM_HAND_SLOTS,
        ).expand(*actions.shape, NUM_HAND_SLOTS)
        new_slots = expanded_inverse.gather(-1, old_slots.unsqueeze(-1)).squeeze(-1)
        remapped = new_slots * NUM_TILES + actions.remainder(NUM_TILES)
        return torch.where(placement, remapped, actions)

    return (
        replace(
            inputs,
            hand_ids=hand_ids,
            hand_levels=hand_levels,
            hand_level_confidence=hand_level_confidence,
            hand_id_confidence=hand_id_confidence,
            action_mask=action_mask,
            previous_actions=remap_actions(inputs.previous_actions),
            critic_card_ids=critic_card_ids,
        ),
        remap_actions(targets),
    )


def _sample_hand_permutation_orders(
    rng: np.random.Generator,
    *,
    batch_size: int,
    probability: float,
) -> np.ndarray:
    """Sample sequence-level hand relabelings with an explicit mixture dose."""

    if batch_size <= 0:
        raise ValueError("batch size must be positive")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between zero and one")
    identity = np.arange(NUM_HAND_SLOTS, dtype=np.int64)
    if probability == 0.0:
        return np.tile(identity, (batch_size, 1))
    if probability == 1.0:
        return np.stack(
            [rng.permutation(NUM_HAND_SLOTS) for _ in range(batch_size)]
        )
    orders = np.tile(identity, (batch_size, 1))
    selected = rng.random(batch_size) < probability
    for row in np.flatnonzero(selected):
        orders[row] = rng.permutation(NUM_HAND_SLOTS)
    return orders


def _hierarchical_imitation_breakdown(
    output: Any,
    targets: torch.Tensor,
    action_masks: torch.Tensor,
    trusted: torch.Tensor,
    *,
    decision_sample_weights: torch.Tensor | None = None,
    card_sample_weights: torch.Tensor | None = None,
    tile_sample_weights: torch.Tensor | None = None,
) -> Any:
    action_type_logits = output.action_type_logits.reshape(
        -1, NUM_HAND_SLOTS + 2
    )
    decision_logits = torch.cat(
        [
            torch.logsumexp(
                action_type_logits[:, :NUM_HAND_SLOTS], dim=-1, keepdim=True
            ),
            action_type_logits[:, NUM_HAND_SLOTS:],
        ],
        dim=-1,
    )
    placement = (targets >= 0) & (targets < PLACEMENT_ACTIONS)
    labels = labels_from_flat_actions(
        targets,
        decision_trusted=trusted,
        card_trusted=trusted & placement,
        tile_trusted=trusted & placement,
    )
    masks = factor_public_action_mask(action_masks)
    breakdown = hierarchical_masked_imitation_loss(
        decision_logits,
        action_type_logits[:, :NUM_HAND_SLOTS],
        output.location_logits.reshape(-1, NUM_HAND_SLOTS, NUM_TILES),
        masks,
        labels,
        config=HierarchicalImitationConfig(),
        decision_sample_weights=decision_sample_weights,
        card_sample_weights=card_sample_weights,
        tile_sample_weights=tile_sample_weights,
    )
    return breakdown, decision_logits, masks, labels


@torch.no_grad()
def evaluate_imitation(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    indices: np.ndarray,
    *,
    batch_size: int,
    device: torch.device,
    objective: str = "exact",
    spatial_semantics: TokenSpatialSemantics | None = None,
    spatial_config: SpatialImitationConfig | None = None,
    trim_entity_padding: bool = False,
) -> dict[str, float]:
    if objective not in IMITATION_OBJECTIVES:
        raise ValueError(f"unknown imitation objective {objective!r}")
    if spatial_semantics is None:
        raise ValueError("spatial semantics are required for imitation evaluation")
    spatial_config = spatial_config or SpatialImitationConfig()
    model.eval()
    sums: dict[str, float] = {
        "loss": 0.0,
        "exact_loss": 0.0,
        "action_type_loss": 0.0,
        "location_loss": 0.0,
    }
    hierarchical_loss_sums = {"decision": 0.0, "card": 0.0, "tile": 0.0}
    hierarchical_counts = {"decision": 0.0, "card": 0.0, "tile": 0.0}
    hierarchical_metrics: dict[str, float] = {}
    metric_totals: dict[str, float] = {}
    for batch_indices, inputs, output in _imitation_evaluation_batches(
        model, arrays, indices, batch_size=batch_size, device=device,
        trim_entity_padding=trim_entity_padding,
    ):
        targets = torch.as_tensor(
            arrays["expert_actions"][batch_indices], dtype=torch.long, device=device
        )
        logits = output.joint_logits[:, 0]
        breakdown = factorized_spatial_imitation_loss(
            logits,
            targets,
            inputs.action_mask[:, 0],
            inputs.hand_ids[:, 0],
            spatial_semantics,
            config=spatial_config,
            reduction="sum",
        )
        if objective == HIERARCHICAL_OBJECTIVE:
            trusted = torch.ones_like(targets, dtype=torch.bool)
            hierarchical, decision_logits, public_masks, labels = (
                _hierarchical_imitation_breakdown(
                    output,
                    targets,
                    inputs.action_mask[:, 0],
                    trusted,
                )
            )
            for name in ("decision", "card", "tile"):
                count = float(getattr(hierarchical, f"{name}_count"))
                hierarchical_counts[name] += count
                hierarchical_loss_sums[name] += float(
                    getattr(hierarchical, name)
                ) * count
            component_metrics = hierarchical_imitation_metric_sums(
                decision_logits,
                output.action_type_logits[:, 0, :NUM_HAND_SLOTS],
                output.location_logits[:, 0],
                public_masks,
                labels,
            )
            for name, value in component_metrics.items():
                hierarchical_metrics[name] = hierarchical_metrics.get(
                    name, 0.0
                ) + float(value)
        elif objective in SLOT_CHOICE_OBJECTIVES:
            slot_choice_loss = conditional_slot_choice_loss(
                output.action_type_logits[:, 0],
                targets,
                inputs.action_mask[:, 0],
                reduction="sum",
            )
            sums["loss"] += float(slot_choice_loss)
            sums["action_type_loss"] += float(slot_choice_loss)
        else:
            sums["loss"] += float(
                breakdown.exact_joint if objective == "exact" else breakdown.total
            )
            sums["action_type_loss"] += float(breakdown.action_type)
        sums["exact_loss"] += float(breakdown.exact_joint)
        sums["location_loss"] += float(breakdown.location)
        batch_metrics = imitation_metric_sums(
            logits,
            targets,
            inputs.action_mask[:, 0],
            inputs.hand_ids[:, 0],
            spatial_semantics,
        )
        for name, value in batch_metrics.items():
            metric_totals[name] = metric_totals.get(name, 0.0) + float(value)

    samples = max(1.0, metric_totals.get("samples", 0.0))
    placements = max(1.0, metric_totals.get("placement_samples", 0.0))
    distance_count = max(1.0, metric_totals.get("correct_slot_distance_count", 0.0))
    results = {name: value / samples for name, value in sums.items()}
    if objective == HIERARCHICAL_OBJECTIVE:
        component_means = {
            name: hierarchical_loss_sums[name]
            / max(1.0, hierarchical_counts[name])
            for name in ("decision", "card", "tile")
        }
        results["loss"] = sum(component_means.values())
        results["action_type_loss"] = component_means["decision"]
        results["card_loss"] = component_means["card"]
        results["location_loss"] = component_means["tile"]
        for name in ("decision", "play", "wait", "ability", "card"):
            count = hierarchical_metrics.get(f"{name}_count", 0.0)
            results[f"hierarchical_{name}_accuracy"] = (
                hierarchical_metrics.get(f"{name}_correct", 0.0)
                / max(1.0, count)
            )
            results[f"hierarchical_{name}_samples"] = count
        tile_count = hierarchical_metrics.get("tile_count", 0.0)
        results["hierarchical_tile_exact_accuracy"] = (
            hierarchical_metrics.get("tile_exact_correct", 0.0)
            / max(1.0, tile_count)
        )
        results["hierarchical_tile_within_one_accuracy"] = (
            hierarchical_metrics.get("tile_within_one_correct", 0.0)
            / max(1.0, tile_count)
        )
        results["hierarchical_tile_samples"] = tile_count
    results.update(
        {
            "accuracy": metric_totals.get("exact_correct", 0.0) / samples,
            "action_type_accuracy": metric_totals.get("type_correct", 0.0) / samples,
            "slot_accuracy": metric_totals.get("correct_slot", 0.0) / placements,
            "within_1_tile_accuracy": metric_totals.get("within_1_tile", 0.0)
            / placements,
            "within_2_tiles_accuracy": metric_totals.get("within_2_tiles", 0.0)
            / placements,
            "mechanic_tolerant_accuracy": metric_totals.get(
                "mechanic_tolerant_correct", 0.0
            )
            / samples,
            "correct_slot_mean_distance": metric_totals.get(
                "correct_slot_distance_sum", 0.0
            )
            / distance_count,
            "samples": metric_totals.get("samples", 0.0),
            "placement_samples": metric_totals.get("placement_samples", 0.0),
        }
    )
    for kind in ("troop", "building", "spell"):
        count = metric_totals.get(f"{kind}_samples", 0.0)
        denom = max(1.0, count)
        results[f"{kind}_samples"] = count
        for metric in ("exact", "type", "tolerant"):
            results[f"{kind}_{metric}_accuracy"] = (
                metric_totals.get(f"{kind}_{metric}_correct", 0.0) / denom
            )
    return results


def conditional_slot_choice_loss(
    action_type_logits: torch.Tensor,
    targets: torch.Tensor,
    action_mask: torch.Tensor,
    *,
    reduction: str,
) -> torch.Tensor:
    """Cross entropy among legal hand slots, independent of play timing."""

    placement_mask = action_mask[..., :PLACEMENT_ACTIONS].reshape(
        *action_mask.shape[:-1], NUM_HAND_SLOTS, NUM_TILES
    )
    legal_slots = placement_mask.any(dim=-1)
    masked_logits = action_type_logits[..., :NUM_HAND_SLOTS].masked_fill(
        ~legal_slots, -1e9
    )
    slot_targets = targets.clamp(max=PLACEMENT_ACTIONS - 1) // NUM_TILES
    return nn.functional.cross_entropy(
        masked_logits.reshape(-1, NUM_HAND_SLOTS),
        slot_targets.reshape(-1),
        reduction=reduction,
    )


def _checkpoint_payload(
    *,
    model: ClasherPolicy,
    metadata: CorpusMetadata,
    corpus_path: Path,
    metrics: dict[str, float],
    seed: int,
    split_seed: int,
    trained: bool,
    initial_checkpoint: Path | None = None,
    source_update: int = 0,
    source_total_transitions: int = 0,
    imitation_objective: str = "exact",
    spatial_config: SpatialImitationConfig | None = None,
    left_right_augmentation: bool = False,
    hand_permutation_augmentation: bool = False,
    hand_permutation_augmentation_probability: float = 1.0,
    trim_entity_padding: bool = False,
    trainable_prefixes: Sequence[str] = (),
    anchor_policy_kl_coef: float = 0.0,
    expert_card_balance_power: float = 0.0,
    max_expert_card_weight: float = 4.0,
    expert_action_type_balance_power: float = 0.0,
    max_expert_action_type_weight: float = 3.0,
    max_combined_sample_weight: float = 16.0,
    defensive_context_weight: float = 1.0,
    defensive_context_maximum_y: float = 0.25,
    canonical_lane_globals: bool = False,
) -> dict[str, Any]:
    if initial_checkpoint is None:
        if trained and metadata.label_source == "human-replay":
            initialization = "human_replay_imitation"
        else:
            initialization = ("public_script_imitation" if metadata.label_source == "public-script" else "oracle_imitation") if trained else "matched_random_control"
    else:
        if trained and metadata.label_source == "human-replay":
            initialization = "human_replay_imitation_finetune"
        else:
            initialization = (
                "oracle_imitation_finetune" if trained else "initial_checkpoint_control"
            )
    trainable_scope: str | list[str] = (
        list(trainable_prefixes)
        if trainable_prefixes
        else (
            "action_type_head"
            if imitation_objective == TYPE_HEAD_OBJECTIVE
            else (
                "safe_slot_choice_adapter"
                if imitation_objective == SAFE_SLOT_CHOICE_OBJECTIVE
                else (
                    "semantic_slot_choice_query"
                    if imitation_objective == SEMANTIC_SLOT_CHOICE_OBJECTIVE
                    else "all_parameters"
                )
            )
        )
    )
    return {
        "format_version": 2,
        "model_type": "entity_spatial_recurrent",
        "model_config": model.config.to_dict(),
        "token_names": metadata.token_names,
        "model_state_dict": model.state_dict(),
        "args": {
            "initialization": initialization,
            "initial_checkpoint": (
                str(initial_checkpoint) if initial_checkpoint is not None else None
            ),
            "corpus": str(corpus_path),
            "seed": seed,
            "split_seed": split_seed,
            "imitation_objective": imitation_objective,
            "trainable_scope": trainable_scope,
            "left_right_augmentation": left_right_augmentation,
            "hand_permutation_augmentation": hand_permutation_augmentation,
            "hand_permutation_augmentation_probability": (
                hand_permutation_augmentation_probability
            ),
            "trim_entity_padding": trim_entity_padding,
            "anchor_policy_kl_coef": anchor_policy_kl_coef,
            "expert_card_balance_power": expert_card_balance_power,
            "max_expert_card_weight": max_expert_card_weight,
            "expert_action_type_balance_power": expert_action_type_balance_power,
            "max_expert_action_type_weight": max_expert_action_type_weight,
            "max_combined_sample_weight": max_combined_sample_weight,
            "defensive_context_weight": defensive_context_weight,
            "defensive_context_maximum_y": defensive_context_maximum_y,
        },
        "update": source_update,
        "total_transitions": source_total_transitions,
        "metrics": metrics,
        "imitation": {
            "schema_version": 1,
            "corpus": str(corpus_path),
            "corpus_samples": metadata.samples,
            "reward_profile": metadata.reward_profile,
            "trained": trained,
            "initial_checkpoint": (
                str(initial_checkpoint) if initial_checkpoint is not None else None
            ),
            "objective": imitation_objective,
            "trainable_scope": trainable_scope,
            "spatial_config": asdict(spatial_config or SpatialImitationConfig()),
            "left_right_augmentation": left_right_augmentation,
            "hand_permutation_augmentation": hand_permutation_augmentation,
            "hand_permutation_augmentation_probability": (
                hand_permutation_augmentation_probability
            ),
            "trim_entity_padding": trim_entity_padding,
            "anchor_policy_kl_coef": anchor_policy_kl_coef,
            "expert_card_balance_power": expert_card_balance_power,
            "max_expert_card_weight": max_expert_card_weight,
            "expert_action_type_balance_power": expert_action_type_balance_power,
            "max_expert_action_type_weight": max_expert_action_type_weight,
            "max_combined_sample_weight": max_combined_sample_weight,
            "defensive_context_weight": defensive_context_weight,
            "defensive_context_maximum_y": defensive_context_maximum_y,
        },
    }


def fit_imitation_corpus(
    *,
    corpus_path: Path,
    output_checkpoint: Path,
    control_checkpoint: Path,
    decks_path: Path,
    seed: int,
    split_seed: int | None = None,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    validation_fraction: float,
    device: torch.device,
    d_model: int,
    num_heads: int,
    actor_layers: int,
    critic_layers: int,
    memory_size: int,
    encoder_kind: str = "attention",
    decoder_kind: str = "attention",
    memory_kind: str = "lstm",
    card_input_mode: str = "hybrid",
    card_semantics_version: int = 1,
    initial_checkpoint: Path | None = None,
    model_config_override: PolicyConfig | None = None,
    checkpoint_metadata: dict[str, Any] | None = None,
    train_on_forced_actions: bool = False,
    imitation_objective: str = "exact",
    spatial_config: SpatialImitationConfig | None = None,
    sequence_length: int = 1,
    recurrent_update_mode: str = "full-prefix",
    tbptt_chunk: int = 64,
    tbptt_burn_in: int = 16,
    left_right_augmentation: bool = False,
    hand_permutation_augmentation: bool = False,
    hand_permutation_augmentation_probability: float = 1.0,
    trim_entity_padding: bool = False,
    placement_actions_only: bool = False,
    trainable_prefixes: Sequence[str] = (),
    anchor_policy_kl_coef: float = 0.0,
    expert_card_balance_power: float = 0.0,
    max_expert_card_weight: float = 4.0,
    expert_action_type_balance_power: float = 0.0,
    max_expert_action_type_weight: float = 3.0,
    max_combined_sample_weight: float = 16.0,
    defensive_context_weight: float = 1.0,
    defensive_context_maximum_y: float = 0.25,
    canonical_lane_globals: bool = False,
    public_observation_sidecar: Path | None = None,
    equivariant_hand_policy: bool = False,
    equivariant_slot_choice_only: bool = False,
    hierarchical_mode_gate: bool = False,
) -> dict[str, Any]:
    from .tbptt import ImitationStateCache, validate_mode

    validate_mode(recurrent_update_mode, tbptt_chunk, tbptt_burn_in)
    stored_state = recurrent_update_mode == "stored-state"
    if stored_state:
        if tbptt_chunk < 2:
            raise ValueError("imitation TBPTT chunk must be at least two")
        if left_right_augmentation or hand_permutation_augmentation:
            raise ValueError("stored-state fitting requires unaugmented sequences")
        sequence_length = tbptt_chunk
    if checkpoint_metadata:
        allowed = {"gamedata_sha256", "strategy_sha256", "source_pins_sha256", "training_decks_sha256", "admission_sha256", "warmstart_plan_sha256", "resource_budget"}
        if set(checkpoint_metadata) - allowed:
            raise ValueError("unsupported checkpoint provenance fields")
        if any(not isinstance(value, str) or len(value) != 64 or set(value) - set("0123456789abcdef") for key, value in checkpoint_metadata.items() if key != "resource_budget"):
            raise ValueError("checkpoint provenance must contain SHA-256 digests")
        if "resource_budget" in checkpoint_metadata:
            from .council_budget import BudgetSnapshot
            BudgetSnapshot.model_validate(checkpoint_metadata["resource_budget"])
    if epochs <= 0 or batch_size <= 0 or sequence_length <= 0:
        raise ValueError("epochs and batch_size must be positive")
    metadata, arrays = load_corpus(corpus_path)
    council_corpus = metadata.public_contract_version >= 4
    if stored_state and not council_corpus:
        raise ValueError("stored-state imitation requires complete public-v4 or later episodes")
    if council_corpus:
        provenance = json.loads(metadata.provenance or "{}")
        if provenance.get("role") != "training":
            raise ValueError("public-v4 fitting requires an explicit training data role")
        if sequence_length <= 1:
            raise ValueError("public-v4 imitation requires recurrent sequences")
        if left_right_augmentation or hand_permutation_augmentation:
            raise ValueError("council exact-prefix fitting currently requires unaugmented sequences")
        if any((expert_card_balance_power, expert_action_type_balance_power)) or defensive_context_weight != 1.0:
            raise ValueError("council script warm start preserves the natural timing prior")
        if placement_actions_only:
            raise ValueError("council script warm start must preserve waits")
        card_semantics_version = 4
        canonical_lane_globals = True
    if public_observation_sidecar is not None:
        arrays = load_public_observation_sidecar(
            public_observation_sidecar,
            base_arrays=arrays,
        )
    if imitation_objective not in IMITATION_OBJECTIVES:
        raise ValueError(f"unknown imitation objective {imitation_objective!r}")
    if anchor_policy_kl_coef < 0.0:
        raise ValueError("anchor policy KL coefficient must be non-negative")
    if anchor_policy_kl_coef > 0.0 and initial_checkpoint is None:
        raise ValueError("anchor policy KL requires an initial checkpoint")
    if not 0.0 <= expert_card_balance_power <= 1.0:
        raise ValueError("expert card balance power must be between zero and one")
    if max_expert_card_weight < 1.0:
        raise ValueError("maximum expert card weight must be at least one")
    if not 0.0 <= expert_action_type_balance_power <= 1.0:
        raise ValueError("expert action type balance power must be between zero and one")
    if max_expert_action_type_weight < 1.0:
        raise ValueError("maximum expert action type weight must be at least one")
    if max_combined_sample_weight < 1.0:
        raise ValueError("maximum combined sample weight must be at least one")
    if defensive_context_weight < 1.0:
        raise ValueError("defensive context weight must be at least one")
    if not 0.0 <= defensive_context_maximum_y <= 1.0:
        raise ValueError("defensive context maximum y must be between zero and one")
    if not 0.0 <= hand_permutation_augmentation_probability <= 1.0:
        raise ValueError(
            "hand permutation augmentation probability must be between zero and one"
        )
    if card_semantics_version not in {1, 2, 3, 4}:
        raise ValueError("card_semantics_version must be 1, 2, 3, or 4")
    if equivariant_hand_policy and equivariant_slot_choice_only:
        raise ValueError(
            "equivariant hand policy and slot-choice-only policy are mutually exclusive"
        )
    if equivariant_hand_policy and hierarchical_mode_gate:
        raise ValueError(
            "legacy equivariant hand timing and hierarchical mode gate are mutually exclusive"
        )
    if (equivariant_hand_policy or equivariant_slot_choice_only) and (
        initial_checkpoint is not None
    ):
        raise ValueError(
            "equivariant hand policies are fresh-initialization architectures"
        )
    spatial_config = spatial_config or SpatialImitationConfig()
    if imitation_objective == TYPE_HEAD_OBJECTIVE:
        spatial_config = replace(spatial_config, location_loss_coef=0.0)
    if imitation_objective in SLOT_CHOICE_OBJECTIVES:
        placement_actions_only = True
    spatial_config.validate()
    initial_payload: dict[str, Any] | None = None
    config: PolicyConfig | None = model_config_override
    upgrade_legacy_confidence = False
    if model_config_override is not None:
        if initial_checkpoint is not None:
            raise ValueError("fresh model config cannot override an initial checkpoint")
        if model_config_override.public_contract_version != metadata.public_contract_version or tuple(model_config_override.public_token_names) != metadata.token_names:
            raise ValueError("fresh model config does not match the corpus public contract")
        if model_config_override.max_entities != metadata.max_entities:
            raise ValueError("fresh model entity capacity differs from corpus")
    if initial_checkpoint is not None:
        initial_payload = torch.load(
            initial_checkpoint, map_location=device, weights_only=False
        )
        if int(initial_payload.get("format_version", 0)) != 2:
            raise ValueError("initial checkpoint is not a V2 policy")
        if tuple(initial_payload["token_names"]) != tuple(metadata.token_names):
            raise ValueError(
                "initial checkpoint token vocabulary does not match corpus"
            )
        config = PolicyConfig.from_dict(initial_payload["model_config"])
        if council_corpus and config.public_contract_version != metadata.public_contract_version:
            raise ValueError("initial checkpoint public contract does not match corpus")
        if config.public_observation_confidence and public_observation_sidecar is None and not council_corpus:
            raise ValueError(
                "confidence-aware checkpoint requires a public observation sidecar"
            )
        if public_observation_sidecar is not None:
            upgrade_legacy_confidence = not config.public_observation_confidence
            config = replace(
                config,
                public_observation_confidence=True,
                actor_observation_domain="causal-frame-v1",
            )
        if canonical_lane_globals:
            config = replace(config, canonical_lane_globals=True)
        if config.max_entities != metadata.max_entities:
            raise ValueError("initial checkpoint max_entities does not match corpus")
    builder = StructuredObservationBuilder(
        decks_path=decks_path,
        max_entities=metadata.max_entities,
        token_names=metadata.token_names,
        card_semantics_version=(
            config.card_semantics_version
            if config is not None
            else card_semantics_version
        ),
        canonical_lane_globals=(
            config.canonical_lane_globals
            if config is not None
            else canonical_lane_globals
        ),
        public_entity_levels=council_corpus or (config is not None and config.public_contract_version >= 3),
        public_hand_levels=council_corpus,
        public_history_slots=(config.public_history_slots if config is not None else metadata.public_history_slots),
        public_seen_card_slots=(
            config.public_seen_card_slots if config is not None else metadata.public_seen_card_slots
        ),
    )
    if config is None:
        equivariant_slot_choice = (
            equivariant_hand_policy or equivariant_slot_choice_only
        )
        config = PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.max_entities,
            card_semantics_version=card_semantics_version,
            public_contract_version=4 if council_corpus else 1,
            public_token_names=builder.token_names if council_corpus else (),
            public_history_slots=metadata.public_history_slots,
            public_seen_card_slots=metadata.public_seen_card_slots,
            d_model=d_model,
            num_heads=num_heads,
            actor_layers=actor_layers,
            critic_layers=critic_layers,
            memory_size=memory_size,
            encoder_kind=encoder_kind,
            decoder_kind=decoder_kind,
            memory_kind=memory_kind,
            card_input_mode=card_input_mode,
            canonical_lane_globals=canonical_lane_globals,
            public_observation_confidence=council_corpus or public_observation_sidecar is not None,
            actor_observation_domain=(
                "causal-frame-v1"
                if council_corpus or public_observation_sidecar is not None
                else "simulator-exact"
            ),
            actor_current_hand_slot_invariant=equivariant_slot_choice,
            semantic_slot_choice_adapter_enabled=equivariant_slot_choice,
            semantic_slot_choice_replace_base=equivariant_slot_choice,
            mechanics_slot_choice_adapter_enabled=equivariant_slot_choice,
            mechanics_slot_choice_replace_base=equivariant_slot_choice,
            equivariant_slot_choice=equivariant_slot_choice,
            equivariant_timing_query_enabled=equivariant_hand_policy,
            hierarchical_mode_gate_enabled=hierarchical_mode_gate,
            deterministic_hierarchy=(
                "play-gate" if hierarchical_mode_gate else "slot"
            ),
        )
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = ClasherPolicy(config, builder.card_stat_features).to(device)
    spatial_semantics = build_token_spatial_semantics(
        builder,
        device=device,
        config=spatial_config,
    )
    if initial_payload is not None:
        load_policy_state_with_confidence_upgrade(
            model,
            initial_payload["model_state_dict"],
            upgrade_legacy_confidence=upgrade_legacy_confidence,
        )
    anchor_model: ClasherPolicy | None = None
    if anchor_policy_kl_coef > 0.0:
        assert initial_payload is not None
        anchor_model = ClasherPolicy(config, builder.card_stat_features).to(device)
        load_policy_state_with_confidence_upgrade(
            anchor_model,
            initial_payload["model_state_dict"],
            upgrade_legacy_confidence=upgrade_legacy_confidence,
        )
        anchor_model.eval()
        for parameter in anchor_model.parameters():
            parameter.requires_grad_(False)
    source_update = int(initial_payload.get("update", 0)) if initial_payload else 0
    source_total_transitions = (
        int(initial_payload.get("total_transitions", 0)) if initial_payload else 0
    )
    trainable_prefixes = tuple(trainable_prefixes)
    if any(not prefix for prefix in trainable_prefixes):
        raise ValueError("trainable parameter prefixes must be non-empty")
    if trainable_prefixes:
        for name, parameter in model.named_parameters():
            parameter.requires_grad_(
                any(name.startswith(prefix) for prefix in trainable_prefixes)
            )
    elif imitation_objective == TYPE_HEAD_OBJECTIVE:
        for name, parameter in model.named_parameters():
            parameter.requires_grad_(name.startswith("action_type_head."))
    elif imitation_objective == SAFE_SLOT_CHOICE_OBJECTIVE:
        for name, parameter in model.named_parameters():
            parameter.requires_grad_(name.startswith("safe_slot_choice_adapter."))
    elif imitation_objective == SEMANTIC_SLOT_CHOICE_OBJECTIVE:
        for name, parameter in model.named_parameters():
            parameter.requires_grad_(name.startswith("semantic_slot_choice_query."))
    trainable_parameters = [
        parameter for parameter in model.parameters() if parameter.requires_grad
    ]
    if not trainable_parameters:
        raise ValueError("imitation objective selected no trainable parameters")
    optimizer = torch.optim.AdamW(trainable_parameters, lr=learning_rate)
    effective_split_seed = seed if split_seed is None else split_seed
    split_groups = arrays.get("source_replays", arrays["episode_ids"])
    if split_groups.shape != arrays["episode_ids"].shape:
        raise ValueError("corpus replay split groups are not aligned")
    if council_corpus and "fit_split" in arrays:
        fit_split = arrays["fit_split"]
        if fit_split.shape != arrays["episode_ids"].shape or not np.isin(fit_split, [0, 1]).all():
            raise ValueError("invalid predefined warm-start fit split")
        all_training, all_validation = np.flatnonzero(fit_split == 0), np.flatnonzero(fit_split == 1)
        for episode in np.unique(arrays["episode_ids"]):
            if len(np.unique(fit_split[arrays["episode_ids"] == episode])) != 1:
                raise ValueError("warm-start fit split crosses an episode")
    else:
        all_training, all_validation = split_indices(
            split_groups,
            validation_fraction=validation_fraction,
            seed=effective_split_seed,
        )
    supervised = imitation_supervision_mask(
        arrays["action_masks"],
        arrays["expert_actions"],
        train_on_forced_actions=train_on_forced_actions,
        placement_actions_only=placement_actions_only,
    )
    if "expert_action_supervision_valid" in arrays:
        supervised &= np.asarray(
            arrays["expert_action_supervision_valid"], dtype=np.bool_
        )
    training = all_training[supervised[all_training]]
    validation = all_validation[supervised[all_validation]]
    if training.size == 0 or validation.size == 0:
        raise ValueError(
            "corpus needs supervised actions in both train and validation episodes"
        )
    card_weights = expert_card_balance_weights(
        arrays["hand_ids"],
        arrays["expert_actions"],
        training,
        power=expert_card_balance_power,
        max_weight=max_expert_card_weight,
    )
    context_mask = visible_enemy_pressure_mask(
        arrays["entity_features"],
        arrays["entity_mask"],
        maximum_canonical_y=defensive_context_maximum_y,
    )
    context_weights = defensive_context_weights(
        arrays["entity_features"],
        arrays["entity_mask"],
        context_weight=defensive_context_weight,
        maximum_canonical_y=defensive_context_maximum_y,
    )
    action_type_weights = expert_action_type_balance_weights(
        arrays["expert_actions"],
        training,
        power=expert_action_type_balance_power,
        max_weight=max_expert_action_type_weight,
    )
    decision_weights = expert_decision_balance_weights(
        arrays["expert_actions"],
        training,
        power=expert_action_type_balance_power,
        max_weight=max_expert_action_type_weight,
    )
    sample_weights = np.minimum(
        card_weights * context_weights * action_type_weights,
        max_combined_sample_weight,
    ).astype(np.float32)
    hierarchical_decision_weights = np.minimum(
        decision_weights * context_weights,
        max_combined_sample_weight,
    ).astype(np.float32)
    hierarchical_card_weights = np.minimum(
        card_weights * context_weights,
        max_combined_sample_weight,
    ).astype(np.float32)

    training_chunks: np.ndarray | None = None
    validation_chunks: np.ndarray | None = None
    if sequence_length > 1:
        training_chunks = sequence_chunks(
            arrays["episode_ids"], all_training, sequence_length=sequence_length, preserve_tails=council_corpus
        )
        validation_chunks = sequence_chunks(
            arrays["episode_ids"], all_validation, sequence_length=sequence_length, preserve_tails=council_corpus
        )

    control_metrics = evaluate_imitation(
        model,
        arrays,
        validation,
        batch_size=batch_size,
        device=device,
        objective=imitation_objective,
        spatial_semantics=spatial_semantics,
        spatial_config=spatial_config,
        trim_entity_padding=trim_entity_padding,
    )
    control_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        _checkpoint_payload(
            model=model,
            metadata=metadata,
            corpus_path=corpus_path,
            metrics={
                f"validation_{key}": value for key, value in control_metrics.items()
            },
            seed=seed,
            split_seed=effective_split_seed,
            trained=False,
            initial_checkpoint=initial_checkpoint,
            source_update=source_update,
            source_total_transitions=source_total_transitions,
            imitation_objective=imitation_objective,
            spatial_config=spatial_config,
            left_right_augmentation=left_right_augmentation,
            hand_permutation_augmentation=hand_permutation_augmentation,
            hand_permutation_augmentation_probability=(
                hand_permutation_augmentation_probability
            ),
            trim_entity_padding=trim_entity_padding,
            trainable_prefixes=trainable_prefixes,
            anchor_policy_kl_coef=anchor_policy_kl_coef,
            expert_card_balance_power=expert_card_balance_power,
            max_expert_card_weight=max_expert_card_weight,
            expert_action_type_balance_power=expert_action_type_balance_power,
            max_expert_action_type_weight=max_expert_action_type_weight,
            max_combined_sample_weight=max_combined_sample_weight,
            defensive_context_weight=defensive_context_weight,
            defensive_context_maximum_y=defensive_context_maximum_y,
        ) | (checkpoint_metadata or {}) | ({"recurrent_update": {
            "mode": recurrent_update_mode, "chunk": tbptt_chunk, "burn_in": tbptt_burn_in,
            "state_refresh": "once-per-epoch"}} if stored_state else {}),
        control_checkpoint,
    )

    episode_offsets = {int(episode): int(np.flatnonzero(arrays["episode_ids"] == episode)[0]) for episode in np.unique(arrays["episode_ids"])} if council_corpus else {}
    if council_corpus:
        for episode, first in episode_offsets.items():
            rows = np.flatnonzero(arrays["episode_ids"] == episode)
            if not arrays["episode_starts"][first] or arrays["terminal_status"][rows[-1]] != 1 or arrays["expert_action_supervision_valid"][rows[-1]]:
                raise ValueError("council fitting needs complete episodes ending in unsupervised terminal context")
    rng = np.random.default_rng(seed + 1)
    fit_started = time.monotonic()
    for epoch in range(epochs):
        state_cache = (ImitationStateCache(model, arrays, training_chunks,
                       episode_offsets=episode_offsets, burn_in=tbptt_burn_in, device=device)
                       if stored_state else None)
        model.train()
        if training_chunks is None:
            shuffled_batches = rng.permutation(training)
            batch_stride = batch_size
        else:
            shuffled_batches = training_chunks[rng.permutation(len(training_chunks))]
            batch_stride = max(1, batch_size // sequence_length)
        for start in range(0, len(shuffled_batches), batch_stride):
            batch_indices = shuffled_batches[start : start + batch_stride]
            if training_chunks is None:
                inputs = _batch_inputs(arrays, batch_indices, device)
            else:
                inputs = _sequence_batch_inputs(
                    arrays,
                    batch_indices,
                    device,
                    trim_entity_padding=trim_entity_padding,
                    reset_memory=not council_corpus,
                )
            targets = torch.as_tensor(
                arrays["expert_actions"][batch_indices], dtype=torch.long, device=device
            )
            if left_right_augmentation:
                inputs, targets = mirror_imitation_batch(
                    inputs,
                    targets,
                    torch.as_tensor(
                        rng.random(inputs.batch_size) < 0.5,
                        dtype=torch.bool,
                        device=device,
                    ),
                )
            if hand_permutation_augmentation:
                orders = torch.as_tensor(
                    _sample_hand_permutation_orders(
                        rng,
                        batch_size=inputs.batch_size,
                        probability=hand_permutation_augmentation_probability,
                    ),
                    dtype=torch.long,
                    device=device,
                )
                inputs, targets = permute_hand_imitation_batch(
                    inputs,
                    targets,
                    orders,
                )
            if state_cache is not None:
                recurrent_state = state_cache.initial_state(model, arrays, batch_indices, device=device)
            else:
                recurrent_state = _council_imitation_state(model, arrays, batch_indices, device=device, episode_offsets=episode_offsets) if council_corpus else None
            model_output = model(inputs, recurrent_state)
            logits = model_output.joint_logits
            flat_logits = logits.reshape(-1, logits.shape[-1])
            flat_targets = targets.reshape(-1)
            if training_chunks is not None:
                supervised_tokens = torch.as_tensor(
                    imitation_supervision_mask(
                        arrays["action_masks"][batch_indices].reshape(
                            -1, arrays["action_masks"].shape[-1]
                        ),
                        arrays["expert_actions"][batch_indices].reshape(-1),
                        train_on_forced_actions=train_on_forced_actions,
                        placement_actions_only=placement_actions_only,
                    ),
                    dtype=torch.bool,
                    device=device,
                )
                if "expert_action_supervision_valid" in arrays:
                    supervised_tokens &= torch.as_tensor(
                        arrays["expert_action_supervision_valid"][
                            batch_indices
                        ].reshape(-1),
                        dtype=torch.bool,
                        device=device,
                    )
                if not bool(supervised_tokens.any()):
                    continue
            else:
                supervised_tokens = torch.ones_like(flat_targets, dtype=torch.bool)
            # Unsupervised recurrent-context rows may carry an expert label that
            # the public mask cannot verify.  Use always-legal no-op only for
            # evaluating the vectorized loss, then exclude those rows below.
            loss_targets = flat_targets.masked_fill(
                ~supervised_tokens,
                NUM_HAND_SLOTS * NUM_TILES,
            )
            batch_weights = torch.as_tensor(
                sample_weights[batch_indices].reshape(-1),
                dtype=flat_logits.dtype,
                device=device,
            )
            if imitation_objective == HIERARCHICAL_OBJECTIVE:
                decision_batch_weights = torch.as_tensor(
                    hierarchical_decision_weights[batch_indices].reshape(-1),
                    dtype=flat_logits.dtype,
                    device=device,
                )
                card_batch_weights = torch.as_tensor(
                    hierarchical_card_weights[batch_indices].reshape(-1),
                    dtype=flat_logits.dtype,
                    device=device,
                )
                hierarchical, _, _, _ = _hierarchical_imitation_breakdown(
                    model_output,
                    flat_targets,
                    inputs.action_mask.reshape(-1, inputs.action_mask.shape[-1]),
                    supervised_tokens,
                    decision_sample_weights=decision_batch_weights,
                    card_sample_weights=card_batch_weights,
                    tile_sample_weights=card_batch_weights,
                )
                loss = hierarchical.total
                per_token = None
            elif imitation_objective == "exact":
                per_token = nn.functional.cross_entropy(
                    flat_logits, loss_targets, reduction="none"
                )
            elif imitation_objective in SLOT_CHOICE_OBJECTIVES:
                per_token = conditional_slot_choice_loss(
                    model_output.action_type_logits.reshape(
                        -1, NUM_HAND_SLOTS + 2
                    ),
                    loss_targets,
                    inputs.action_mask.reshape(-1, inputs.action_mask.shape[-1]),
                    reduction="none",
                )
            else:
                per_token = factorized_spatial_imitation_loss(
                    flat_logits,
                    loss_targets,
                    inputs.action_mask.reshape(-1, inputs.action_mask.shape[-1]),
                    inputs.hand_ids.reshape(-1, inputs.hand_ids.shape[-1]),
                    spatial_semantics,
                    config=spatial_config,
                    reduction="none",
                ).total
            if per_token is not None:
                batch_weights = batch_weights.to(per_token.dtype)
                selected_weights = batch_weights[supervised_tokens]
                loss = (
                    per_token[supervised_tokens] * selected_weights
                ).sum() / selected_weights.sum().clamp_min(1e-12)
            if anchor_model is not None:
                with torch.no_grad():
                    anchor_logits = anchor_model(inputs).joint_logits
                loss = loss + anchor_policy_kl_coef * policy_anchor_kl(
                    logits, anchor_logits
                )
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError(
                    "non-finite imitation loss "
                    f"at epoch {epoch + 1}, batch {start // batch_stride + 1}"
                )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            gradient_norm = nn.utils.clip_grad_norm_(trainable_parameters, 0.5)
            if not bool(torch.isfinite(gradient_norm)):
                raise FloatingPointError(
                    "non-finite imitation gradient norm "
                    f"at epoch {epoch + 1}, batch {start // batch_stride + 1}"
                )
            optimizer.step()
        print(
            json.dumps(
                {
                    "completed_epoch": epoch + 1,
                    "epochs": epochs,
                    "elapsed_seconds": round(time.monotonic() - fit_started, 1),
                }
            ),
            flush=True,
        )

    train_metrics = evaluate_imitation(
        model,
        arrays,
        training,
        batch_size=batch_size,
        device=device,
        objective=imitation_objective,
        spatial_semantics=spatial_semantics,
        spatial_config=spatial_config,
        trim_entity_padding=trim_entity_padding,
    )
    validation_metrics = evaluate_imitation(
        model,
        arrays,
        validation,
        batch_size=batch_size,
        device=device,
        objective=imitation_objective,
        spatial_semantics=spatial_semantics,
        spatial_config=spatial_config,
        trim_entity_padding=trim_entity_padding,
    )
    metrics = {
        **{f"train_{key}": value for key, value in train_metrics.items()},
        **{f"validation_{key}": value for key, value in validation_metrics.items()},
        "control_validation_loss": control_metrics["loss"],
        "control_validation_accuracy": control_metrics["accuracy"],
    }
    output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        _checkpoint_payload(
            model=model,
            metadata=metadata,
            corpus_path=corpus_path,
            metrics=metrics,
            seed=seed,
            split_seed=effective_split_seed,
            trained=True,
            initial_checkpoint=initial_checkpoint,
            source_update=source_update,
            source_total_transitions=source_total_transitions,
            imitation_objective=imitation_objective,
            spatial_config=spatial_config,
            left_right_augmentation=left_right_augmentation,
            hand_permutation_augmentation=hand_permutation_augmentation,
            hand_permutation_augmentation_probability=(
                hand_permutation_augmentation_probability
            ),
            trim_entity_padding=trim_entity_padding,
            trainable_prefixes=trainable_prefixes,
            anchor_policy_kl_coef=anchor_policy_kl_coef,
            expert_card_balance_power=expert_card_balance_power,
            max_expert_card_weight=max_expert_card_weight,
            expert_action_type_balance_power=expert_action_type_balance_power,
            max_expert_action_type_weight=max_expert_action_type_weight,
            max_combined_sample_weight=max_combined_sample_weight,
            defensive_context_weight=defensive_context_weight,
            defensive_context_maximum_y=defensive_context_maximum_y,
        ) | (checkpoint_metadata or {}) | ({"recurrent_update": {
            "mode": recurrent_update_mode, "chunk": tbptt_chunk, "burn_in": tbptt_burn_in,
            "state_refresh": "once-per-epoch"}} if stored_state else {}),
        output_checkpoint,
    )
    return {
        "schema_version": 1,
        "corpus": str(corpus_path),
        "public_observation_sidecar": (
            str(public_observation_sidecar)
            if public_observation_sidecar is not None
            else None
        ),
        "public_observation_sidecar_sha256": (
            file_sha256(public_observation_sidecar)
            if public_observation_sidecar is not None
            else None
        ),
        "imitation_checkpoint": str(output_checkpoint),
        "matched_control_checkpoint": str(control_checkpoint),
        "initial_checkpoint": (
            str(initial_checkpoint) if initial_checkpoint is not None else None
        ),
        "seed": seed,
        "split_seed": effective_split_seed,
        "split_group_source": (
            "source_replays" if "source_replays" in arrays else "episode_ids"
        ),
        "train_samples": len(training),
        "validation_samples": len(validation),
        "epochs": epochs,
        "train_on_forced_actions": train_on_forced_actions,
        "placement_actions_only": placement_actions_only,
        "corpus_samples": metadata.samples,
        "imitation_objective": imitation_objective,
        "trainable_scope": (
            list(trainable_prefixes)
            if trainable_prefixes
            else (
                "action_type_head"
                if imitation_objective == TYPE_HEAD_OBJECTIVE
                else (
                    "safe_slot_choice_adapter"
                    if imitation_objective == SAFE_SLOT_CHOICE_OBJECTIVE
                    else (
                        "semantic_slot_choice_query"
                        if imitation_objective == SEMANTIC_SLOT_CHOICE_OBJECTIVE
                        else "all_parameters"
                    )
                )
            )
        ),
        "sequence_length": sequence_length,
        "recurrence": "stored-state-tbptt" if stored_state else "current-weight-full-episode-prefix" if council_corpus else "legacy-chunk-reset",
        **({"tbptt_chunk": tbptt_chunk, "tbptt_burn_in": tbptt_burn_in} if stored_state else {}),
        "predefined_fit_split": council_corpus and "fit_split" in arrays,
        "left_right_augmentation": left_right_augmentation,
        "hand_permutation_augmentation": hand_permutation_augmentation,
        "hand_permutation_augmentation_probability": (
            hand_permutation_augmentation_probability
        ),
        "trim_entity_padding": trim_entity_padding,
        "anchor_policy_kl_coef": anchor_policy_kl_coef,
        "expert_card_balance_power": expert_card_balance_power,
        "max_expert_card_weight": max_expert_card_weight,
        "expert_action_type_balance_power": expert_action_type_balance_power,
        "max_expert_action_type_weight": max_expert_action_type_weight,
        "max_combined_sample_weight": max_combined_sample_weight,
        "defensive_context_weight": defensive_context_weight,
        "defensive_context_maximum_y": defensive_context_maximum_y,
        "defensive_context_train_samples": int(np.sum(context_mask[training])),
        "defensive_context_validation_samples": int(
            np.sum(context_mask[validation])
        ),
        "canonical_lane_globals": config.canonical_lane_globals,
        "equivariant_hand_policy": (
            config.equivariant_slot_choice
            and config.equivariant_timing_query_enabled
        ),
        "equivariant_slot_choice_only": (
            config.equivariant_slot_choice
            and not config.equivariant_timing_query_enabled
        ),
        "hierarchical_mode_gate": config.hierarchical_mode_gate_enabled,
        "deterministic_hierarchy": config.deterministic_hierarchy,
        "expert_card_weight_min": float(sample_weights[training].min()),
        "expert_card_weight_max": float(sample_weights[training].max()),
        "training_sequences": (
            len(training_chunks) if training_chunks is not None else 0
        ),
        "validation_sequences": (
            len(validation_chunks) if validation_chunks is not None else 0
        ),
        "spatial_config": asdict(spatial_config),
        "metrics": metrics,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build fixed oracle corpora and matched V2 imitation warm starts"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    collect = subparsers.add_parser("collect")
    collect.add_argument("--output", required=True)
    collect.add_argument("--decks-path", default="decks.json")
    collect.add_argument(
        "--sampling-decks-path",
        help=(
            "optional deck pool used for episodes while --decks-path remains "
            "the fixed observation vocabulary"
        ),
    )
    collect.add_argument("--decisions", type=int, default=5000)
    collect.add_argument("--seed", type=int, default=4401)
    collect.add_argument("--decision-interval", type=int, default=8)
    collect.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    collect.add_argument("--planner-depth", type=int, default=6)
    collect.add_argument("--planner-simulations", type=int, default=32)
    collect.add_argument("--planner-action-samples", type=int, default=64)
    collect.add_argument("--max-entities", type=int, default=128)
    collect.add_argument("--workers", type=int, default=1)
    collect.add_argument(
        "--behavior-checkpoint",
        default=None,
        help="V2 policy used to visit states while the oracle supplies labels",
    )
    collect.add_argument(
        "--expert-probability",
        type=float,
        default=1.0,
        help="per-player probability of executing the oracle instead of behavior action",
    )
    collect.add_argument(
        "--reward-profile", choices=REWARD_PROFILES, default=DEFENSE_V2
    )
    collect.add_argument(
        "--stable-root-candidates",
        action="store_true",
        help="reuse one evaluated root action subset and never label unseen arms",
    )
    collect.add_argument(
        "--behavior-opponent",
        default=None,
        help=(
            "stationary opponent for alternating-seat behavior collection: "
            "random or strategy:<name>"
        ),
    )
    collect.add_argument(
        "--label-source",
        choices=LABEL_SOURCES,
        default="oracle",
        help="supervision target: planner oracle or deterministic behavior policy",
    )
    collect.add_argument(
        "--label-strategy",
        default=None,
        help=(
            "deterministic strategy labeler such as strategy:balanced; valid "
            "only with --label-source strategy"
        ),
    )
    collect.add_argument("--quiet-engine", action="store_true", default=True)
    collect.add_argument("--no-quiet-engine", dest="quiet_engine", action="store_false")

    fit = subparsers.add_parser("fit")
    fit.add_argument("--corpus", required=True)
    fit.add_argument(
        "--public-observation-sidecar",
        default=None,
        help=(
            "aligned confidence-aware public-state v2 observations; preserves "
            "the source corpus and upgrades legacy checkpoints fail-closed"
        ),
    )
    fit.add_argument("--output-checkpoint", required=True)
    fit.add_argument("--control-checkpoint", required=True)
    fit.add_argument("--manifest-out", required=True)
    fit.add_argument(
        "--initial-checkpoint",
        default=None,
        help="V2 checkpoint whose weights and update counters are fine-tuned",
    )
    fit.add_argument("--decks-path", default="decks.json")
    fit.add_argument("--seed", type=int, default=5501)
    fit.add_argument(
        "--split-seed",
        type=int,
        default=None,
        help=(
            "episode split seed; defaults to --seed, but can be fixed while "
            "varying initialization and training order across repeat trials"
        ),
    )
    fit.add_argument("--epochs", type=int, default=10)
    fit.add_argument("--batch-size", type=int, default=32)
    fit.add_argument("--learning-rate", type=float, default=2.5e-4)
    fit.add_argument("--validation-fraction", type=float, default=0.2)
    fit.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    fit.add_argument("--d-model", type=int, default=128)
    fit.add_argument("--num-heads", type=int, default=4)
    fit.add_argument("--actor-layers", type=int, default=4)
    fit.add_argument("--critic-layers", type=int, default=2)
    fit.add_argument("--memory-size", type=int, default=256)
    fit.add_argument(
        "--encoder-kind",
        choices=("attention", "deepsets"),
        default="attention",
        help="entity interaction encoder for a fresh imitation model",
    )
    fit.add_argument(
        "--memory-kind",
        choices=("lstm", "gru", "structured", "feedforward"),
        default="lstm",
        help=(
            "temporal core; structured uses a model-owned clock, elixir belief, "
            "and input-driven leaky state without dense recurrent mixing"
        ),
    )
    fit.add_argument(
        "--decoder-kind",
        choices=("attention", "global"),
        default="attention",
        help="tile decoder; global removes cross-attention over entity tokens",
    )
    fit.add_argument(
        "--card-input-mode",
        choices=("hybrid", "residual-hybrid", "id-only", "mechanics-only"),
        default="hybrid",
        help="learned identity, exact mechanics, or both",
    )
    fit.add_argument(
        "--card-semantics-version",
        type=int,
        choices=(1, 2, 3),
        default=1,
        help="public card descriptor schema for a fresh imitation model",
    )
    fit.add_argument("--sequence-length", type=int, default=1)
    fit.add_argument("--recurrent-update-mode", choices=("full-prefix", "stored-state"), default=argparse.SUPPRESS)
    fit.add_argument("--tbptt-chunk", type=int, default=argparse.SUPPRESS)
    fit.add_argument("--tbptt-burn-in", type=int, default=argparse.SUPPRESS)
    fit.add_argument("--recurrent-config", type=Path, default=argparse.SUPPRESS)
    fit.add_argument(
        "--left-right-augmentation",
        action="store_true",
        help="randomly mirror training sequences across the arena's vertical axis",
    )
    fit.add_argument(
        "--hand-permutation-augmentation",
        action="store_true",
        help=(
            "randomly relabel all four current-hand slots once per recurrent "
            "sequence while remapping masks, previous actions, and targets"
        ),
    )
    fit.add_argument(
        "--hand-permutation-augmentation-probability",
        type=float,
        default=1.0,
        help=(
            "fraction of recurrent training sequences receiving an exact "
            "hand-slot relabeling when hand permutation augmentation is enabled"
        ),
    )
    fit.add_argument(
        "--trim-entity-padding",
        action="store_true",
        help=(
            "crop packed trailing entity padding on CPU before sequence batches "
            "are copied to the learner device"
        ),
    )
    fit.add_argument(
        "--train-on-forced-actions",
        action="store_true",
        help="include rows with only one legal action in optimization and metrics",
    )
    fit.add_argument(
        "--placement-actions-only",
        action="store_true",
        help=(
            "advance complete recurrent sequences but supervise only expert "
            "placement actions"
        ),
    )
    fit.add_argument(
        "--imitation-objective",
        choices=IMITATION_OBJECTIVES,
        default="exact",
    )
    fit.add_argument(
        "--type-loss-coef",
        type=float,
        default=1.0,
        help="action-type term weight for spatial-v1 imitation",
    )
    fit.add_argument(
        "--location-loss-coef",
        type=float,
        default=1.0,
        help="conditional placement-location term weight for spatial-v1 imitation",
    )
    fit.add_argument(
        "--trainable-prefix",
        action="append",
        default=[],
        help=(
            "restrict fine-tuning to parameter names beginning with this prefix; "
            "repeat for multiple prefixes"
        ),
    )
    fit.add_argument(
        "--anchor-policy-kl-coef",
        type=float,
        default=0.0,
        help=(
            "forward-KL coefficient preserving the initial checkpoint's full "
            "action distribution during supervised fine-tuning"
        ),
    )
    fit.add_argument(
        "--expert-card-balance-power",
        type=float,
        default=0.0,
        help=(
            "inverse-frequency exponent for expert-played card loss weights; "
            "zero disables balancing and 0.5 applies square-root balancing"
        ),
    )
    fit.add_argument(
        "--max-expert-card-weight",
        type=float,
        default=4.0,
        help="maximum normalized loss weight for an expert-played card",
    )
    fit.add_argument(
        "--expert-action-type-balance-power",
        type=float,
        default=0.0,
        help=(
            "inverse-frequency exponent across four card slots, wait, and "
            "ability; zero disables action-type balancing"
        ),
    )
    fit.add_argument(
        "--max-expert-action-type-weight",
        type=float,
        default=3.0,
        help="maximum normalized loss weight for an expert action type",
    )
    fit.add_argument(
        "--max-combined-sample-weight",
        type=float,
        default=16.0,
        help="cap after multiplying card, action-type, and context weights",
    )
    fit.add_argument(
        "--defensive-context-weight",
        type=float,
        default=1.0,
        help=(
            "relative human-imitation loss weight when a visible enemy troop "
            "or building is near the defended side"
        ),
    )
    fit.add_argument(
        "--defensive-context-maximum-y",
        type=float,
        default=0.25,
        help="maximum canonical enemy y for defensive-context weighting",
    )
    fit.add_argument(
        "--canonical-lane-globals",
        action="store_true",
        help=(
            "version new checkpoints to swap left/right tower globals for the "
            "canonical player-one perspective"
        ),
    )
    fit.add_argument(
        "--equivariant-hand-policy",
        action="store_true",
        help=(
            "for a fresh model, treat the current hand as an unordered set, "
            "score cards with shared semantic/mechanics queries, and learn a "
            "separate permutation-invariant play/wait/ability timing head"
        ),
    )
    fit.add_argument(
        "--equivariant-slot-choice-only",
        action="store_true",
        help=(
            "use exact permutation-equivariant conditional card choice while "
            "retaining the invariant aggregate timing pool instead of a learned "
            "replacement timing query"
        ),
    )
    fit.add_argument(
        "--hierarchical-mode-gate",
        action="store_true",
        help=(
            "learn one play/wait/ability gate and condition the existing card "
            "selector on play; combine with --equivariant-slot-choice-only for F3"
        ),
    )
    from .tbptt import apply_cli_config
    return apply_cli_config(parser.parse_args())


def main() -> None:
    args = parse_args()
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    if args.command == "collect":
        metadata = collect_oracle_corpus(
            output_path=resolve_path(args.output),
            decks_path=decks_path,
            decisions=args.decisions,
            seed=args.seed,
            decision_interval=args.decision_interval,
            max_ticks=args.max_ticks,
            planner_depth=args.planner_depth,
            planner_simulations=args.planner_simulations,
            planner_action_samples=args.planner_action_samples,
            max_entities=args.max_entities,
            quiet_engine=args.quiet_engine,
            reward_profile=args.reward_profile,
            workers=args.workers,
            behavior_checkpoint=(
                resolve_path(args.behavior_checkpoint, must_exist=True)
                if args.behavior_checkpoint
                else None
            ),
            expert_probability=args.expert_probability,
            stable_root_candidates=args.stable_root_candidates,
            behavior_opponent=args.behavior_opponent,
            label_source=args.label_source,
            label_strategy=args.label_strategy,
            sampling_decks_path=(
                resolve_decks_path(args.sampling_decks_path, must_exist=True)
                if args.sampling_decks_path is not None
                else None
            ),
        )
        print(metadata.to_json())
        return

    device = resolve_learner_device(args.device)
    spatial_config = SpatialImitationConfig(
        type_loss_coef=args.type_loss_coef,
        location_loss_coef=args.location_loss_coef,
    )
    manifest = fit_imitation_corpus(
        corpus_path=resolve_path(args.corpus, must_exist=True),
        output_checkpoint=resolve_path(args.output_checkpoint),
        control_checkpoint=resolve_path(args.control_checkpoint),
        decks_path=decks_path,
        seed=args.seed,
        split_seed=args.split_seed,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        validation_fraction=args.validation_fraction,
        device=device,
        d_model=args.d_model,
        num_heads=args.num_heads,
        actor_layers=args.actor_layers,
        critic_layers=args.critic_layers,
        memory_size=args.memory_size,
        encoder_kind=args.encoder_kind,
        decoder_kind=args.decoder_kind,
        memory_kind=args.memory_kind,
        card_input_mode=args.card_input_mode,
        card_semantics_version=args.card_semantics_version,
        initial_checkpoint=(
            resolve_path(args.initial_checkpoint, must_exist=True)
            if args.initial_checkpoint
            else None
        ),
        train_on_forced_actions=args.train_on_forced_actions,
        imitation_objective=args.imitation_objective,
        spatial_config=spatial_config,
        sequence_length=args.sequence_length,
        recurrent_update_mode=getattr(args, "recurrent_update_mode", "full-prefix"),
        tbptt_chunk=getattr(args, "tbptt_chunk", 64),
        tbptt_burn_in=getattr(args, "tbptt_burn_in", 16),
        left_right_augmentation=args.left_right_augmentation,
        hand_permutation_augmentation=args.hand_permutation_augmentation,
        hand_permutation_augmentation_probability=(
            args.hand_permutation_augmentation_probability
        ),
        trim_entity_padding=args.trim_entity_padding,
        placement_actions_only=args.placement_actions_only,
        trainable_prefixes=args.trainable_prefix,
        anchor_policy_kl_coef=args.anchor_policy_kl_coef,
        expert_card_balance_power=args.expert_card_balance_power,
        max_expert_card_weight=args.max_expert_card_weight,
        expert_action_type_balance_power=args.expert_action_type_balance_power,
        max_expert_action_type_weight=args.max_expert_action_type_weight,
        max_combined_sample_weight=args.max_combined_sample_weight,
        defensive_context_weight=args.defensive_context_weight,
        defensive_context_maximum_y=args.defensive_context_maximum_y,
        canonical_lane_globals=args.canonical_lane_globals,
        public_observation_sidecar=(
            resolve_path(args.public_observation_sidecar, must_exist=True)
            if args.public_observation_sidecar
            else None
        ),
        equivariant_hand_policy=args.equivariant_hand_policy,
        equivariant_slot_choice_only=args.equivariant_slot_choice_only,
        hierarchical_mode_gate=args.hierarchical_mode_gate,
    )
    manifest_path = resolve_path(args.manifest_out)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
