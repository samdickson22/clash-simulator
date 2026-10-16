from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import math
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass, fields, replace
from functools import wraps
from pathlib import Path
from typing import Any, Literal, ParamSpec, TypeVar, cast

import numpy as np
import torch
from torch import Tensor, nn
from torch.nn import functional as F

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.paths import (
    checkpoints_dir,
    resolve_path,
)
from clasher.paths import (
    decks_path as resolve_decks_path,
)

from .causal_rehearsal import CausalDecisionRehearsal
from .common import NUM_HAND_SLOTS, NUM_TILES
from .imitation_objective import (
    PLACEMENT_ACTIONS,
    SpatialImitationConfig,
    TokenSpatialSemantics,
    build_token_spatial_semantics,
    factorized_spatial_imitation_loss,
)
from .model import ClasherPolicy, PolicyConfig, PolicyInputs, PolicyOutput
from .reward_model import OBJECTIVE_V1, REWARD_PROFILES
from .rollout_audit import write_rollout_audit
from .selfplay_env import SelfPlayBattleEnv, resolve_match_horizon
from .strategy_bots import (
    STRATEGY_NAMES,
    BalancedStrategyConfig,
    StrategyBot,
    allocate_pfsp_slots,
)
from .structured_obs import StructuredObservation, StructuredObservationBuilder


class _NullWriter:
    def write(self, _value: Any) -> int:
        return 0

    def flush(self) -> None:
        return None


_NULL_WRITER = _NullWriter()
# Experimental until the authoritative-branch random and strategy screens agree.
_USE_ROLLOUT_INFERENCE_MODE = False
_USE_TRIMMED_ROLLOUT_ENTITY_PADDING = False
PUBLIC_BELIEF_PARAMETER_PREFIXES = (
    "public_history_",
    "public_seen_card_",
    "public_belief_",
)
_P = ParamSpec("_P")
_R = TypeVar("_R")


def _rollout_grad_mode(function: Callable[_P, _R]) -> Callable[_P, _R]:
    """Select benchmarkable inference-only execution for actor rollouts."""

    @wraps(function)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        context = (
            torch.inference_mode() if _USE_ROLLOUT_INFERENCE_MODE else torch.no_grad()
        )
        with context:
            return function(*args, **kwargs)

    return wrapped


@contextmanager
def maybe_silence_stdio(enabled: bool) -> Iterator[None]:
    if not enabled:
        yield
        return
    with redirect_stdout(_NULL_WRITER), redirect_stderr(_NULL_WRITER):
        yield


@dataclass
class RolloutBatch:
    entity_ids: np.ndarray
    entity_features: np.ndarray
    entity_mask: np.ndarray
    hand_ids: np.ndarray
    global_features: np.ndarray
    entity_id_confidence: np.ndarray
    entity_feature_confidence: np.ndarray
    hand_id_confidence: np.ndarray
    global_feature_confidence: np.ndarray
    opponent_history_ids: np.ndarray
    opponent_history_ages: np.ndarray
    opponent_seen_card_ids: np.ndarray
    opponent_play_event_ids: np.ndarray
    opponent_play_event_confidence: np.ndarray
    action_masks: np.ndarray
    previous_actions: np.ndarray
    previous_rewards: np.ndarray
    episode_starts: np.ndarray
    critic_entity_ids: np.ndarray
    critic_entity_features: np.ndarray
    critic_entity_mask: np.ndarray
    critic_card_ids: np.ndarray
    critic_global_features: np.ndarray
    actions: np.ndarray
    old_log_probs: np.ndarray
    old_values: np.ndarray
    rewards: np.ndarray
    dones: np.ndarray
    initial_hidden: np.ndarray
    initial_cell: np.ndarray
    bootstrap_values: np.ndarray
    episodes_finished: int
    wins: int
    losses: int
    draws: int
    action_success: np.ndarray | None = None
    recurrent_prefixes: tuple[PolicyInputs | None, ...] | None = None
    truncation_bootstrap_values: np.ndarray | None = None
    strategy_teacher_actions: np.ndarray | None = None
    entity_levels: np.ndarray | None = None
    entity_level_confidence: np.ndarray | None = None
    hand_levels: np.ndarray | None = None
    hand_level_confidence: np.ndarray | None = None
    own_last_play_ids: np.ndarray | None = None
    own_last_play_features: np.ndarray | None = None

    stored_hidden: np.ndarray | None = None
    stored_cell: np.ndarray | None = None
    burn_in_prefixes: tuple[PolicyInputs | None, ...] | None = None
    burn_in_hidden: np.ndarray | None = None
    burn_in_cell: np.ndarray | None = None
    burn_in_states_hidden: np.ndarray | None = None
    burn_in_states_cell: np.ndarray | None = None

    @property
    def num_sequences(self) -> int:
        return int(self.actions.shape[0])

    @property
    def sequence_length(self) -> int:
        return int(self.actions.shape[1])

    @property
    def transitions(self) -> int:
        return int(self.actions.size)


@dataclass
class PlacementRehearsal:
    """Episode-contiguous expert actions sampled as an auxiliary PPO task."""

    source: Path
    arrays: dict[str, np.ndarray]
    chunks: np.ndarray
    spatial_semantics: TokenSpatialSemantics
    rng: np.random.Generator
    loss_component: Literal["joint", "location", "type"] = "joint"

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        builder: StructuredObservationBuilder,
        device: torch.device,
        sequence_length: int,
        seed: int,
        loss_component: Literal["joint", "location", "type"] = "joint",
    ) -> PlacementRehearsal:
        if sequence_length <= 0:
            raise ValueError("rehearsal sequence length must be positive")
        if loss_component not in {"joint", "location", "type"}:
            raise ValueError(
                "rehearsal loss component must be joint, location, or type"
            )
        names = (
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
        with np.load(path, allow_pickle=False) as payload:
            metadata = json.loads(str(payload["metadata_json"].item()))
            arrays = {name: payload[name].copy() for name in names}
        if tuple(metadata["token_names"]) != tuple(builder.token_names):
            raise ValueError("rehearsal corpus token vocabulary differs")
        if int(metadata["max_entities"]) != builder.max_entities:
            raise ValueError("rehearsal corpus max_entities differs")
        samples = int(arrays["expert_actions"].shape[0])
        if any(array.shape[0] != samples for array in arrays.values()):
            raise ValueError("rehearsal corpus arrays have different lengths")
        legal = arrays["action_masks"][np.arange(samples), arrays["expert_actions"]]
        if not np.all(legal):
            raise ValueError("rehearsal corpus contains an illegal expert action")

        episode_ids = arrays["episode_ids"]
        chunks: list[np.ndarray] = []
        start = 0
        while start < samples:
            end = start + 1
            while end < samples and episode_ids[end] == episode_ids[start]:
                end += 1
            for chunk_start in range(start, end - sequence_length + 1, sequence_length):
                chunk: np.ndarray = np.arange(
                    chunk_start, chunk_start + sequence_length, dtype=np.int64
                )
                targets = arrays["expert_actions"][chunk]
                informative = (
                    np.count_nonzero(arrays["action_masks"][chunk], axis=-1) > 1
                )
                supervised = (
                    informative
                    if loss_component == "type"
                    else (targets < PLACEMENT_ACTIONS) & informative
                )
                if np.any(supervised):
                    chunks.append(chunk)
            start = end
        if not chunks:
            raise ValueError("rehearsal corpus has no supervised sequence chunks")
        return cls(
            source=path,
            arrays=arrays,
            chunks=np.stack(chunks),
            spatial_semantics=build_token_spatial_semantics(
                builder, device=device, config=SpatialImitationConfig()
            ),
            rng=np.random.default_rng(seed),
            loss_component=loss_component,
        )

    def loss(
        self,
        model: ClasherPolicy,
        *,
        device: torch.device,
        batch_sequences: int,
    ) -> Tensor:
        if batch_sequences <= 0:
            raise ValueError("rehearsal batch size must be positive")
        selected = self.chunks[
            self.rng.integers(0, len(self.chunks), size=batch_sequences)
        ]

        def tensor(name: str, dtype: torch.dtype) -> Tensor:
            return torch.as_tensor(
                self.arrays[name][selected], dtype=dtype, device=device
            )

        inputs = PolicyInputs(
            entity_ids=tensor("entity_ids", torch.long),
            entity_features=tensor("entity_features", torch.float32),
            entity_mask=tensor("entity_mask", torch.bool),
            hand_ids=tensor("hand_ids", torch.long),
            global_features=tensor("global_features", torch.float32),
            action_mask=tensor("action_masks", torch.bool),
            previous_actions=tensor("previous_actions", torch.long),
            previous_rewards=tensor("previous_rewards", torch.float32),
            episode_starts=tensor("episode_starts", torch.bool),
        )
        if model.config.public_observation_confidence:
            inputs = inputs.with_exact_actor_confidence()
        targets = tensor("expert_actions", torch.long)
        output = model(inputs)
        flat_logits = output.joint_logits.reshape(-1, output.joint_logits.shape[-1])
        flat_targets = targets.reshape(-1)
        flat_masks = inputs.action_mask.reshape(-1, inputs.action_mask.shape[-1])
        flat_hands = inputs.hand_ids.reshape(-1, inputs.hand_ids.shape[-1])
        informative = flat_masks.count_nonzero(dim=-1) > 1
        supervised = (
            informative
            if self.loss_component == "type"
            else (flat_targets < PLACEMENT_ACTIONS) & informative
        )
        breakdown = factorized_spatial_imitation_loss(
            flat_logits,
            flat_targets,
            flat_masks,
            flat_hands,
            self.spatial_semantics,
            reduction="none",
        )
        if self.loss_component == "location":
            losses = breakdown.location
        elif self.loss_component == "type":
            losses = breakdown.action_type
        else:
            losses = breakdown.total
        return losses[supervised].mean()

    def anchor_policy_kl(
        self,
        model: ClasherPolicy,
        anchor_model: ClasherPolicy,
        *,
        device: torch.device,
        batch_sequences: int,
    ) -> Tensor:
        """Preserve a frozen policy on sampled recurrent corpus states."""

        if batch_sequences <= 0:
            raise ValueError("rehearsal batch size must be positive")
        selected = self.chunks[
            self.rng.integers(0, len(self.chunks), size=batch_sequences)
        ]

        def tensor(name: str, dtype: torch.dtype) -> Tensor:
            return torch.as_tensor(
                self.arrays[name][selected], dtype=dtype, device=device
            )

        inputs = PolicyInputs(
            entity_ids=tensor("entity_ids", torch.long),
            entity_features=tensor("entity_features", torch.float32),
            entity_mask=tensor("entity_mask", torch.bool),
            hand_ids=tensor("hand_ids", torch.long),
            global_features=tensor("global_features", torch.float32),
            action_mask=tensor("action_masks", torch.bool),
            previous_actions=tensor("previous_actions", torch.long),
            previous_rewards=tensor("previous_rewards", torch.float32),
            episode_starts=tensor("episode_starts", torch.bool),
        )
        if model.config.public_observation_confidence:
            inputs = inputs.with_exact_actor_confidence()
        output = model(inputs)
        with torch.no_grad():
            anchor_output = anchor_model(inputs)
        return factorized_policy_anchor_kl(
            output,
            anchor_output,
            inputs.action_mask,
            component=self.loss_component,
        )


def resolve_torch_device(name: str) -> torch.device:
    if name == "cpu":
        return torch.device("cpu")
    if name == "mps":
        if not torch.backends.mps.is_available():
            raise RuntimeError("MPS requested but unavailable")
        return torch.device("mps")
    if name == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        return torch.device("cuda")
    if torch.cuda.is_available():
        return torch.device("cuda")
    # Small recurrent/entity-attention inference batches are substantially
    # faster on Apple CPU than MPS because GPU launch overhead dominates.
    return torch.device("cpu")


def resolve_learner_device(name: str) -> torch.device:
    """Choose a device for full-sequence PPO updates.

    Acting consists of tiny, latency-sensitive batches and stays faster on the
    Apple CPU.  PPO consumes complete recurrent sequences, where MPS has enough
    work per launch to be useful.  Keep the generic resolver CPU-biased for
    evaluation and acting, while allowing the trainer's auto mode to use MPS.
    """

    if name != "auto":
        return resolve_torch_device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


@torch.no_grad()
def synchronize_actor_model(
    learner_model: ClasherPolicy,
    actor_model: ClasherPolicy,
) -> None:
    """Copy the latest learner parameters to a possibly different device."""

    if learner_model is actor_model:
        return
    actor_model.load_state_dict(learner_model.state_dict())


def _public_extension_arrays(
    observations: list[StructuredObservation],
    builder: StructuredObservationBuilder | None = None,
) -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {}
    for observation in observations:
        for prefix in ("entity", "hand"):
            levels = getattr(observation, f"{prefix}_levels", None)
            confidence = getattr(observation, f"{prefix}_level_confidence", None)
            if (levels is None) != (confidence is None):
                raise ValueError(
                    f"{prefix} levels and confidence must be supplied together"
                )
    for name in (
        "entity_levels",
        "entity_level_confidence",
        "hand_levels",
        "hand_level_confidence",
    ):
        values = [getattr(observation, name, None) for observation in observations]
        if any(value is not None for value in values):
            if not all(value is not None for value in values):
                raise ValueError(f"mixed public contract for {name}")
            arrays[name] = np.stack(values)
    if builder is not None and getattr(builder, "public_contract_version", 1) >= 2:
        accepted = [observation.own_last_play for observation in observations]
        ids = np.asarray(
            [
                0
                if item is None
                else builder.token_id(item.card_name, namespace="card_action")
                for item in accepted
            ],
            dtype=np.int64,
        )
        if np.any(ids == 1):
            raise ValueError("accepted own card is outside the declared vocabulary")
        arrays["own_last_play_ids"] = ids
        arrays["own_last_play_features"] = np.asarray(
            [
                [
                    float(item is not None),
                    0.0 if item is None else item.elixir_cost / 10,
                ]
                for item in accepted
            ],
            dtype=np.float32,
        )
    return arrays


def _stack_step_inputs(
    observations: list[StructuredObservation],
    action_masks: np.ndarray,
    previous_actions: np.ndarray,
    previous_rewards: np.ndarray,
    episode_starts: np.ndarray,
    device: torch.device,
    *,
    public_observation_confidence: bool = False,
    builder: StructuredObservationBuilder | None = None,
) -> PolicyInputs:
    actor_width: int | None = None
    critic_width: int | None = None
    if _USE_TRIMMED_ROLLOUT_ENTITY_PADDING:

        def trailing_width(name: str) -> int:
            width = 1
            for observation in observations:
                valid = np.flatnonzero(getattr(observation, name))
                if valid.size:
                    width = max(width, int(valid[-1]) + 1)
            return width

        actor_width = trailing_width("entity_mask")
        critic_width = trailing_width("critic_entity_mask")

    def stack(name: str, dtype: torch.dtype) -> Tensor:
        array = np.stack([getattr(observation, name) for observation in observations])
        if name.startswith("critic_entity_") and critic_width is not None:
            array = array[:, :critic_width]
        elif name.startswith("entity_") and actor_width is not None:
            array = array[:, :actor_width]
        return torch.as_tensor(array, dtype=dtype, device=device).unsqueeze(1)

    event_ids, event_confidence = _current_opponent_play_events(observations)

    inputs = PolicyInputs(
        entity_ids=stack("entity_ids", torch.long),
        entity_features=stack("entity_features", torch.float32),
        entity_mask=stack("entity_mask", torch.bool),
        hand_ids=stack("hand_ids", torch.long),
        global_features=stack("global_features", torch.float32),
        opponent_history_ids=stack("opponent_history_ids", torch.long),
        opponent_history_ages=stack("opponent_history_ages", torch.float32),
        opponent_seen_card_ids=stack("opponent_seen_card_ids", torch.long),
        opponent_play_event_ids=torch.as_tensor(
            event_ids, dtype=torch.long, device=device
        ).unsqueeze(1),
        opponent_play_event_confidence=torch.as_tensor(
            event_confidence, dtype=torch.float32, device=device
        ).unsqueeze(1),
        action_mask=torch.as_tensor(
            action_masks, dtype=torch.bool, device=device
        ).unsqueeze(1),
        previous_actions=torch.as_tensor(
            previous_actions, dtype=torch.long, device=device
        ).unsqueeze(1),
        previous_rewards=torch.as_tensor(
            previous_rewards, dtype=torch.float32, device=device
        ).unsqueeze(1),
        episode_starts=torch.as_tensor(
            episode_starts, dtype=torch.bool, device=device
        ).unsqueeze(1),
        critic_entity_ids=stack("critic_entity_ids", torch.long),
        critic_entity_features=stack("critic_entity_features", torch.float32),
        critic_entity_mask=stack("critic_entity_mask", torch.bool),
        critic_card_ids=stack("critic_card_ids", torch.long),
        critic_global_features=stack("critic_global_features", torch.float32),
    )
    extensions = _public_extension_arrays(observations, builder)
    if actor_width is not None:
        extensions = {
            name: value[:, :actor_width] if name.startswith("entity_") else value
            for name, value in extensions.items()
        }
    inputs = replace(
        inputs,
        **{
            name: torch.as_tensor(value, device=device).unsqueeze(1)
            for name, value in extensions.items()
        },
    )
    if not public_observation_confidence:
        return inputs
    confidence_names = (
        "entity_id_confidence",
        "entity_feature_confidence",
        "hand_id_confidence",
        "global_feature_confidence",
    )
    supplied = [
        all(getattr(observation, name) is not None for observation in observations)
        for name in confidence_names
    ]
    if all(supplied):
        return replace(
            inputs,
            entity_id_confidence=stack("entity_id_confidence", torch.float32),
            entity_feature_confidence=stack("entity_feature_confidence", torch.float32),
            hand_id_confidence=stack("hand_id_confidence", torch.float32),
            global_feature_confidence=stack("global_feature_confidence", torch.float32),
        )
    if any(supplied):
        raise ValueError("structured actor confidence must be supplied together")
    return inputs.with_exact_actor_confidence()


def _empty_rollout_arrays(
    *,
    agents: int,
    steps: int,
    builder: StructuredObservationBuilder,
    num_actions: int,
) -> dict[str, np.ndarray]:
    spec = builder.spec
    arrays = {
        "entity_ids": np.zeros((agents, steps, spec.max_entities), dtype=np.int64),
        "entity_features": np.zeros(
            (agents, steps, spec.max_entities, spec.entity_feature_size),
            dtype=np.float32,
        ),
        "entity_mask": np.zeros((agents, steps, spec.max_entities), dtype=np.bool_),
        "hand_ids": np.zeros((agents, steps, 5), dtype=np.int64),
        "global_features": np.zeros(
            (agents, steps, spec.actor_global_size), dtype=np.float32
        ),
        "entity_id_confidence": np.zeros(
            (agents, steps, spec.max_entities), dtype=np.float32
        ),
        "entity_feature_confidence": np.zeros(
            (agents, steps, spec.max_entities, spec.entity_feature_size),
            dtype=np.float32,
        ),
        "hand_id_confidence": np.zeros((agents, steps, 5), dtype=np.float32),
        "global_feature_confidence": np.zeros(
            (agents, steps, spec.actor_global_size), dtype=np.float32
        ),
        "opponent_history_ids": np.zeros(
            (agents, steps, spec.public_history_slots), dtype=np.int64
        ),
        "opponent_history_ages": np.zeros(
            (agents, steps, spec.public_history_slots), dtype=np.float32
        ),
        "opponent_seen_card_ids": np.zeros(
            (agents, steps, spec.public_seen_card_slots), dtype=np.int64
        ),
        "opponent_play_event_ids": np.zeros((agents, steps), dtype=np.int64),
        "opponent_play_event_confidence": np.zeros((agents, steps), dtype=np.float32),
        "action_masks": np.zeros((agents, steps, num_actions), dtype=np.bool_),
        "previous_actions": np.zeros((agents, steps), dtype=np.int64),
        "previous_rewards": np.zeros((agents, steps), dtype=np.float32),
        "episode_starts": np.zeros((agents, steps), dtype=np.bool_),
        "critic_entity_ids": np.zeros(
            (agents, steps, spec.max_entities), dtype=np.int64
        ),
        "critic_entity_features": np.zeros(
            (agents, steps, spec.max_entities, spec.entity_feature_size),
            dtype=np.float32,
        ),
        "critic_entity_mask": np.zeros(
            (agents, steps, spec.max_entities), dtype=np.bool_
        ),
        "critic_card_ids": np.zeros((agents, steps, 10), dtype=np.int64),
        "critic_global_features": np.zeros(
            (agents, steps, spec.critic_global_size), dtype=np.float32
        ),
        "actions": np.zeros((agents, steps), dtype=np.int64),
        "old_log_probs": np.zeros((agents, steps), dtype=np.float32),
        "old_values": np.zeros((agents, steps), dtype=np.float32),
        "rewards": np.zeros((agents, steps), dtype=np.float32),
        "dones": np.zeros((agents, steps), dtype=np.bool_),
        "action_success": np.ones((agents, steps), dtype=np.bool_),
        "truncation_bootstrap_values": np.zeros((agents, steps), dtype=np.float32),
    }

    if getattr(builder, "public_contract_version", 1) >= 2:
        arrays["own_last_play_ids"] = np.zeros((agents, steps), dtype=np.int64)
        arrays["own_last_play_features"] = np.zeros(
            (agents, steps, 2), dtype=np.float32
        )
    for prefix, size, enabled in (
        ("entity", spec.max_entities, spec.public_entity_levels),
        ("hand", 5, getattr(spec, "public_hand_levels", False)),
    ):
        if enabled:
            arrays[f"{prefix}_levels"] = np.zeros((agents, steps, size), dtype=np.int64)
            arrays[f"{prefix}_level_confidence"] = np.zeros(
                (agents, steps, size), dtype=np.float32
            )
    return arrays


def _store_observations(
    arrays: dict[str, np.ndarray],
    observations: list[StructuredObservation],
    action_masks: np.ndarray,
    previous_actions: np.ndarray,
    previous_rewards: np.ndarray,
    episode_starts: np.ndarray,
    step: int,
    *,
    builder: StructuredObservationBuilder | None = None,
) -> None:
    extensions = _public_extension_arrays(observations, builder)
    for name, value in extensions.items():
        if name not in arrays:
            raise ValueError(f"rollout builder omitted observed field {name}")
        arrays[name][:, step] = value
    for name in ("entity_levels", "hand_levels"):
        if name in arrays and name not in extensions:
            raise ValueError(f"observation omitted required {name}")
    observation_fields = (
        "entity_ids",
        "entity_features",
        "entity_mask",
        "hand_ids",
        "global_features",
        "opponent_history_ids",
        "opponent_history_ages",
        "opponent_seen_card_ids",
        "critic_entity_ids",
        "critic_entity_features",
        "critic_entity_mask",
        "critic_card_ids",
        "critic_global_features",
    )
    for field in observation_fields:
        arrays[field][:, step] = np.stack(
            [getattr(observation, field) for observation in observations]
        )
    event_ids, event_confidence = _current_opponent_play_events(observations)
    arrays["opponent_play_event_ids"][:, step] = event_ids
    arrays["opponent_play_event_confidence"][:, step] = event_confidence
    for observation_index, observation in enumerate(observations):
        entity_known = observation.entity_mask.astype(np.float32, copy=False)
        arrays["entity_id_confidence"][observation_index, step] = (
            entity_known
            if observation.entity_id_confidence is None
            else observation.entity_id_confidence
        )
        arrays["entity_feature_confidence"][observation_index, step] = (
            np.broadcast_to(entity_known[..., None], observation.entity_features.shape)
            if observation.entity_feature_confidence is None
            else observation.entity_feature_confidence
        )
        arrays["hand_id_confidence"][observation_index, step] = (
            1.0
            if observation.hand_id_confidence is None
            else observation.hand_id_confidence
        )
        arrays["global_feature_confidence"][observation_index, step] = (
            1.0
            if observation.global_feature_confidence is None
            else observation.global_feature_confidence
        )
    arrays["action_masks"][:, step] = action_masks
    arrays["previous_actions"][:, step] = previous_actions
    arrays["previous_rewards"][:, step] = previous_rewards
    arrays["episode_starts"][:, step] = episode_starts


def _current_opponent_play_events(
    observations: list[StructuredObservation],
) -> tuple[np.ndarray, np.ndarray]:
    """Adapt exact simulator teacher history to current-frame event pulses.

    This adapter is only a training/simulator label source.  The deployed
    policy interface consumes these two current-frame tensors directly from
    its visual event encoder and never receives the simulator's accumulated
    ``public_card_play_history``.
    """

    event_ids = np.zeros((len(observations),), dtype=np.int64)
    confidence = np.zeros((len(observations),), dtype=np.float32)
    for index, observation in enumerate(observations):
        if not observation.opponent_history_ids.size:
            continue
        card_id = int(observation.opponent_history_ids[0])
        age = float(observation.opponent_history_ages[0])
        # History age is normalized by 60 seconds.  A one-second pulse is long
        # enough to cross the normal 0.4-second policy cadence; the model-owned
        # rising-edge latch deduplicates the repeated visual observation.
        if card_id > 0 and 0.0 <= age <= (1.0 / 60.0 + 1e-7):
            event_ids[index] = card_id
            confidence[index] = 1.0
    return event_ids, confidence


def _current_observations(
    envs: list[SelfPlayBattleEnv],
    *,
    actor_observation_domain: str = "simulator-exact",
) -> tuple[list[StructuredObservation], np.ndarray]:
    observations: list[StructuredObservation] = []
    masks: list[np.ndarray] = []
    for env in envs:
        for player_id in (0, 1):
            observation = env.get_structured_observation(
                player_id,
                actor_observation_domain=actor_observation_domain,
            )
            observations.append(observation)
            masks.append(
                env.get_action_mask(
                    player_id,
                    actor_observation_domain=actor_observation_domain,
                    structured_observation=observation,
                )
            )
    return observations, np.stack(masks)


def _current_learner_observations(
    envs: list[SelfPlayBattleEnv],
    learner_players: tuple[int, ...],
    *,
    actor_observation_domain: str = "simulator-exact",
) -> tuple[list[StructuredObservation], np.ndarray]:
    if len(envs) != len(learner_players):
        raise ValueError("learner_players must have one seat per environment")
    observations: list[StructuredObservation] = []
    masks: list[np.ndarray] = []
    for env, player_id in zip(envs, learner_players):
        observation = env.get_structured_observation(
            player_id,
            actor_observation_domain=actor_observation_domain,
        )
        observations.append(observation)
        masks.append(
            env.get_action_mask(
                player_id,
                actor_observation_domain=actor_observation_domain,
                structured_observation=observation,
            )
        )
    return observations, np.stack(masks)


def _current_action_masks(
    envs: list[SelfPlayBattleEnv],
    players: tuple[int, ...],
) -> np.ndarray:
    if len(envs) != len(players):
        raise ValueError("players must have one seat per environment")
    return np.stack(
        [env.get_action_mask(player_id) for env, player_id in zip(envs, players)]
    )


@_rollout_grad_mode
def collect_rollout(
    *,
    envs: list[SelfPlayBattleEnv],
    builder: StructuredObservationBuilder,
    model: ClasherPolicy,
    device: torch.device,
    rollout_steps: int,
    recurrent_state: tuple[Tensor, Tensor],
    previous_actions: np.ndarray,
    previous_rewards: np.ndarray,
    episode_starts: np.ndarray,
    quiet_engine: bool,
    hazard_conditioned_rollouts: bool = False,
    recurrent_update_mode: str = "full-prefix",
    tbptt_burn_in: int = 16,
) -> tuple[RolloutBatch, tuple[Tensor, Tensor], np.ndarray, np.ndarray, np.ndarray]:
    from .tbptt import RolloutStateRecorder, validate_mode

    validate_mode(recurrent_update_mode, 1, tbptt_burn_in)
    model.eval()
    causal_actor = (
        model.config.public_contract_version >= 4
        or model.config.actor_observation_domain
        in {
            "causal-vision-v1",
            "causal-frame-v1",
        }
    )
    if causal_actor:
        previous_rewards = np.zeros_like(previous_rewards, dtype=np.float32)
    agents = len(envs) * 2
    num_actions = envs[0].action_space.num_actions
    if model.config.public_contract_version >= 4 and any(
        env.public_contract_version != model.config.public_contract_version
        for env in envs
    ):
        raise ValueError(
            "council collection requires matching public environment contracts"
        )
    builder.public_contract_version = model.config.public_contract_version
    arrays = _empty_rollout_arrays(
        agents=agents,
        steps=rollout_steps,
        builder=builder,
        num_actions=num_actions,
    )
    history = None
    recurrent_prefixes = None
    if model.config.public_contract_version >= 4 and recurrent_update_mode == "full-prefix":
        from .council_recurrence import RecurrentHistory, reconstruct_recurrent_state

        history = getattr(model, "_council_rollout_history", None)
        if history is None:
            history = RecurrentHistory(agents)
            model._council_rollout_history = history
        recurrent_prefixes = history.snapshot()
        recurrent_state = reconstruct_recurrent_state(
            model,
            recurrent_prefixes,
            device=device,
        )
    recorder = (RolloutStateRecorder(model, recurrent_state, rollout_steps, tbptt_burn_in)
                if recurrent_update_mode == "stored-state" else None)
    initial_hidden = recurrent_state[0].detach().cpu().numpy().copy()
    initial_cell = recurrent_state[1].detach().cpu().numpy().copy()
    episodes_finished = 0
    wins = losses = draws = 0

    for step in range(rollout_steps):
        with maybe_silence_stdio(quiet_engine):
            observations, action_masks = _current_observations(
                envs,
                actor_observation_domain=model.config.actor_observation_domain,
            )
        _store_observations(
            arrays,
            observations,
            action_masks,
            previous_actions,
            previous_rewards,
            episode_starts,
            step,
            builder=builder,
        )
        inputs = _stack_step_inputs(
            observations,
            action_masks,
            previous_actions,
            previous_rewards,
            episode_starts,
            device,
            public_observation_confidence=model.config.public_observation_confidence,
            builder=builder,
        )
        if recorder is not None:
            recorder.append(inputs, recurrent_state, step)
        if history is not None:
            history.append(inputs)
        actions_t, log_probs_t, values_t, recurrent_state, _ = model.act(
            inputs,
            recurrent_state,
            deterministic=False,
            hazard_conditioned_stochastic=hazard_conditioned_rollouts,
        )
        actions = actions_t[:, 0].cpu().numpy().astype(np.int64, copy=False)
        arrays["actions"][:, step] = actions
        arrays["old_log_probs"][:, step] = log_probs_t[:, 0].cpu().numpy()
        arrays["old_values"][:, step] = values_t[:, 0].cpu().numpy()

        next_previous_actions = actions.copy()
        next_previous_rewards = np.zeros((agents,), dtype=np.float32)
        next_episode_starts = np.zeros((agents,), dtype=np.bool_)
        with maybe_silence_stdio(quiet_engine):
            for env_index, env in enumerate(envs):
                base = 2 * env_index
                rewards, done, step_info = env.step(
                    {0: int(actions[base]), 1: int(actions[base + 1])},
                    pre_action_masks={
                        0: action_masks[base],
                        1: action_masks[base + 1],
                    },
                )
                arrays["rewards"][base, step] = float(rewards[0])
                arrays["rewards"][base + 1, step] = float(rewards[1])
                arrays["dones"][base : base + 2, step] = done
                arrays["action_success"][base : base + 2, step] = [
                    step_info.action_success[0],
                    step_info.action_success[1],
                ]
                if not causal_actor:
                    next_previous_rewards[base] = float(rewards[0])
                    next_previous_rewards[base + 1] = float(rewards[1])
                if (
                    done
                    and step_info.truncated
                    and model.config.public_contract_version >= 4
                ):
                    seats = (0, 1)
                    indices_for_env = np.asarray([base, base + 1])
                    arrays["truncation_bootstrap_values"][indices_for_env, step] = (
                        _truncated_bootstrap(
                            model,
                            env,
                            seats,
                            indices_for_env,
                            recurrent_state,
                            actions,
                            builder,
                            device,
                        )
                    )
                if done:
                    episodes_finished += 1
                    assert env.battle is not None
                    if env.battle.winner is None:
                        draws += 1
                    elif env.battle.winner == 0:
                        wins += 1
                    else:
                        losses += 1
                    env.reset()
                    next_previous_actions[base : base + 2] = (
                        env.action_space.no_op_action
                    )
                    next_previous_rewards[base : base + 2] = 0.0
                    next_episode_starts[base : base + 2] = True

        previous_actions = next_previous_actions
        previous_rewards = next_previous_rewards
        episode_starts = next_episode_starts

    with maybe_silence_stdio(quiet_engine):
        bootstrap_observations, bootstrap_masks = _current_observations(
            envs,
            actor_observation_domain=model.config.actor_observation_domain,
        )
    bootstrap_inputs = _stack_step_inputs(
        bootstrap_observations,
        bootstrap_masks,
        previous_actions,
        previous_rewards,
        episode_starts,
        device,
        public_observation_confidence=model.config.public_observation_confidence,
        builder=builder,
    )
    bootstrap_values = model.forward(bootstrap_inputs, recurrent_state).values[:, 0]

    rollout = RolloutBatch(
        **arrays,
        **(recorder.payload() if recorder is not None else {}),
        recurrent_prefixes=recurrent_prefixes,
        initial_hidden=initial_hidden,
        initial_cell=initial_cell,
        bootstrap_values=bootstrap_values.cpu().numpy(),
        episodes_finished=episodes_finished,
        wins=wins,
        losses=losses,
        draws=draws,
    )
    return (
        rollout,
        (recurrent_state[0].detach(), recurrent_state[1].detach()),
        previous_actions,
        previous_rewards,
        episode_starts,
    )


@_rollout_grad_mode
def collect_rollout_stationary_opponents(
    *,
    envs: list[SelfPlayBattleEnv],
    learner_players: tuple[int, ...],
    builder: StructuredObservationBuilder,
    model: ClasherPolicy,
    device: torch.device,
    rollout_steps: int,
    recurrent_state: tuple[Tensor, Tensor],
    previous_actions: np.ndarray,
    previous_rewards: np.ndarray,
    episode_starts: np.ndarray,
    opponent_model: ClasherPolicy | None,
    opponent_recurrent_state: tuple[Tensor, Tensor] | None,
    opponent_previous_actions: np.ndarray,
    opponent_previous_rewards: np.ndarray,
    opponent_episode_starts: np.ndarray,
    quiet_engine: bool,
    opponent_bot: StrategyBot | None = None,
    learner_teacher_bot: StrategyBot | None = None,
    opponent_noop: bool = False,
    hazard_conditioned_rollouts: bool = False,
    recurrent_update_mode: str = "full-prefix",
    tbptt_burn_in: int = 16,
) -> tuple[
    RolloutBatch,
    tuple[Tensor, Tensor],
    np.ndarray,
    np.ndarray,
    np.ndarray,
    tuple[Tensor, Tensor] | None,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    """Collect one learner seat against a random, scripted, or frozen policy.

    Seats alternate across environments, and only learner-controlled decisions
    enter the rollout. This gives PPO a stationary anchor without contaminating
    the loss with actions sampled by the opponent policy.
    """

    from .tbptt import RolloutStateRecorder, validate_mode

    validate_mode(recurrent_update_mode, 1, tbptt_burn_in)
    model.eval()
    causal_actor = (
        model.config.public_contract_version >= 4
        or model.config.actor_observation_domain
        in {
            "causal-vision-v1",
            "causal-frame-v1",
        }
    )
    if causal_actor:
        previous_rewards = np.zeros_like(previous_rewards, dtype=np.float32)
    if opponent_model is not None:
        opponent_model.eval()
        if opponent_recurrent_state is None:
            raise ValueError("checkpoint opponent requires recurrent state")
        if (
            opponent_model.config.public_contract_version >= 4
            or opponent_model.config.actor_observation_domain
            in {
                "causal-vision-v1",
                "causal-frame-v1",
            }
        ):
            opponent_previous_rewards = np.zeros_like(
                opponent_previous_rewards, dtype=np.float32
            )
    agents = len(envs)
    if agents != len(learner_players):
        raise ValueError("learner_players must have one seat per environment")
    num_actions = envs[0].action_space.num_actions
    if model.config.public_contract_version >= 4 and any(
        env.public_contract_version != model.config.public_contract_version
        for env in envs
    ):
        raise ValueError(
            "council collection requires matching public environment contracts"
        )
    builder.public_contract_version = model.config.public_contract_version
    arrays = _empty_rollout_arrays(
        agents=agents,
        steps=rollout_steps,
        builder=builder,
        num_actions=num_actions,
    )
    history = None
    recurrent_prefixes = None
    if model.config.public_contract_version >= 4 and recurrent_update_mode == "full-prefix":
        from .council_recurrence import RecurrentHistory, reconstruct_recurrent_state

        history = getattr(model, "_council_rollout_history", None)
        if history is None:
            history = RecurrentHistory(agents)
            model._council_rollout_history = history
        recurrent_prefixes = history.snapshot()
        recurrent_state = reconstruct_recurrent_state(
            model,
            recurrent_prefixes,
            device=device,
        )
    recorder = (RolloutStateRecorder(model, recurrent_state, rollout_steps, tbptt_burn_in)
                if recurrent_update_mode == "stored-state" else None)
    initial_hidden = recurrent_state[0].detach().cpu().numpy().copy()
    initial_cell = recurrent_state[1].detach().cpu().numpy().copy()
    episodes_finished = wins = losses = draws = 0
    strategy_teacher_actions = (
        np.empty((agents, rollout_steps), dtype=np.int64)
        if learner_teacher_bot is not None
        else None
    )

    for step in range(rollout_steps):
        with maybe_silence_stdio(quiet_engine):
            observations, action_masks = _current_learner_observations(
                envs,
                learner_players,
                actor_observation_domain=model.config.actor_observation_domain,
            )
        _store_observations(
            arrays,
            observations,
            action_masks,
            previous_actions,
            previous_rewards,
            episode_starts,
            step,
            builder=builder,
        )
        if learner_teacher_bot is not None:
            assert strategy_teacher_actions is not None
            strategy_teacher_actions[:, step] = np.asarray(
                [
                    learner_teacher_bot.select_action(
                        env,
                        player_id,
                        action_mask=mask,
                    )
                    for env, player_id, mask in zip(
                        envs,
                        learner_players,
                        action_masks,
                    )
                ],
                dtype=np.int64,
            )
        inputs = _stack_step_inputs(
            observations,
            action_masks,
            previous_actions,
            previous_rewards,
            episode_starts,
            device,
            public_observation_confidence=model.config.public_observation_confidence,
            builder=builder,
        )
        if recorder is not None:
            recorder.append(inputs, recurrent_state, step)
        if history is not None:
            history.append(inputs)
        actions_t, log_probs_t, values_t, recurrent_state, _ = model.act(
            inputs,
            recurrent_state,
            deterministic=False,
            hazard_conditioned_stochastic=hazard_conditioned_rollouts,
        )
        actions = actions_t[:, 0].cpu().numpy().astype(np.int64, copy=False)
        arrays["actions"][:, step] = actions
        arrays["old_log_probs"][:, step] = log_probs_t[:, 0].cpu().numpy()
        arrays["old_values"][:, step] = values_t[:, 0].cpu().numpy()

        opponent_players = tuple(1 - player_id for player_id in learner_players)
        with maybe_silence_stdio(quiet_engine):
            if opponent_model is None:
                # Random and scripted opponents consume only legal masks. Avoid
                # building their unused public and privileged observation tables.
                opponent_observations = None
                opponent_masks = _current_action_masks(envs, opponent_players)
            else:
                opponent_observations, opponent_masks = _current_learner_observations(
                    envs,
                    opponent_players,
                    actor_observation_domain=(
                        opponent_model.config.actor_observation_domain
                    ),
                )
        if opponent_model is not None:
            assert opponent_observations is not None
            opponent_inputs = _stack_step_inputs(
                opponent_observations,
                opponent_masks,
                opponent_previous_actions,
                opponent_previous_rewards,
                opponent_episode_starts,
                device,
                public_observation_confidence=(
                    opponent_model.config.public_observation_confidence
                ),
                builder=builder,
            )
            (
                opponent_actions_t,
                _,
                _,
                opponent_recurrent_state,
                _,
            ) = opponent_model.act(
                opponent_inputs,
                opponent_recurrent_state,
                deterministic=False,
            )
            opponent_actions = (
                opponent_actions_t[:, 0].cpu().numpy().astype(np.int64, copy=False)
            )
        elif opponent_noop:
            opponent_actions = np.full(
                (agents,), envs[0].action_space.no_op_action, dtype=np.int64
            )
        elif opponent_bot is not None:
            opponent_actions = np.asarray(
                [
                    opponent_bot.select_action(
                        env,
                        player_id,
                        action_mask=mask,
                    )
                    for env, player_id, mask in zip(
                        envs,
                        opponent_players,
                        opponent_masks,
                    )
                ],
                dtype=np.int64,
            )
        else:
            opponent_actions = np.asarray(
                [
                    int(env.np_rng.choice(np.flatnonzero(mask)))
                    if np.any(mask)
                    else env.action_space.no_op_action
                    for env, mask in zip(envs, opponent_masks)
                ],
                dtype=np.int64,
            )

        # A procedural defense episode owns its initial enemy push. The
        # stationary opponent must not add new cards during that short task,
        # while non-scenario environments in the same rollout keep their
        # configured random/scripted/checkpoint opponent. This is what makes a
        # genuine mixed full-game + causal-defense batch possible.
        scenario_opponents = np.asarray(
            [env.defense_scenario is not None for env in envs],
            dtype=np.bool_,
        )
        if np.any(scenario_opponents):
            opponent_actions = opponent_actions.copy()
            opponent_actions[scenario_opponents] = envs[0].action_space.no_op_action

        next_previous_actions = actions.copy()
        next_previous_rewards = np.zeros((agents,), dtype=np.float32)
        next_episode_starts = np.zeros((agents,), dtype=np.bool_)
        next_opponent_previous_actions = opponent_actions.copy()
        next_opponent_previous_rewards = np.zeros((agents,), dtype=np.float32)
        next_opponent_episode_starts = np.zeros((agents,), dtype=np.bool_)
        with maybe_silence_stdio(quiet_engine):
            for env_index, (env, learner_player) in enumerate(
                zip(envs, learner_players)
            ):
                opponent_player = 1 - learner_player
                rewards, done, step_info = env.step(
                    {
                        learner_player: int(actions[env_index]),
                        opponent_player: int(opponent_actions[env_index]),
                    },
                    pre_action_masks={
                        learner_player: action_masks[env_index],
                        opponent_player: opponent_masks[env_index],
                    },
                )
                learner_reward = float(rewards[learner_player])
                arrays["rewards"][env_index, step] = learner_reward
                arrays["dones"][env_index, step] = done
                arrays["action_success"][env_index, step] = step_info.action_success[
                    learner_player
                ]
                if not causal_actor:
                    next_previous_rewards[env_index] = learner_reward
                if (
                    opponent_model is not None
                    and opponent_model.config.public_contract_version < 4
                    and opponent_model.config.actor_observation_domain
                    not in {"causal-vision-v1", "causal-frame-v1"}
                ):
                    next_opponent_previous_rewards[env_index] = float(
                        rewards[opponent_player]
                    )
                if (
                    done
                    and step_info.truncated
                    and model.config.public_contract_version >= 4
                ):
                    indices_for_env = np.asarray([env_index])
                    arrays["truncation_bootstrap_values"][indices_for_env, step] = (
                        _truncated_bootstrap(
                            model,
                            env,
                            (learner_player,),
                            indices_for_env,
                            recurrent_state,
                            actions,
                            builder,
                            device,
                        )
                    )
                if done:
                    episodes_finished += 1
                    assert env.battle is not None
                    if env.battle.winner is None:
                        draws += 1
                    elif env.battle.winner == learner_player:
                        wins += 1
                    else:
                        losses += 1
                    record_outcome = getattr(opponent_bot, "record_outcome", None)
                    if record_outcome is not None:
                        # Monitoring-only per-opponent outcome log.
                        record_outcome(env, learner_player)
                    env.reset()
                    next_previous_actions[env_index] = env.action_space.no_op_action
                    next_previous_rewards[env_index] = 0.0
                    next_episode_starts[env_index] = True
                    next_opponent_previous_actions[env_index] = (
                        env.action_space.no_op_action
                    )
                    next_opponent_previous_rewards[env_index] = 0.0
                    next_opponent_episode_starts[env_index] = True

        previous_actions = next_previous_actions
        previous_rewards = next_previous_rewards
        episode_starts = next_episode_starts
        opponent_previous_actions = next_opponent_previous_actions
        opponent_previous_rewards = next_opponent_previous_rewards
        opponent_episode_starts = next_opponent_episode_starts

    with maybe_silence_stdio(quiet_engine):
        bootstrap_observations, bootstrap_masks = _current_learner_observations(
            envs,
            learner_players,
            actor_observation_domain=model.config.actor_observation_domain,
        )
    bootstrap_inputs = _stack_step_inputs(
        bootstrap_observations,
        bootstrap_masks,
        previous_actions,
        previous_rewards,
        episode_starts,
        device,
        public_observation_confidence=model.config.public_observation_confidence,
        builder=builder,
    )
    bootstrap_values = model.forward(bootstrap_inputs, recurrent_state).values[:, 0]
    rollout = RolloutBatch(
        **arrays,
        **(recorder.payload() if recorder is not None else {}),
        recurrent_prefixes=recurrent_prefixes,
        initial_hidden=initial_hidden,
        initial_cell=initial_cell,
        bootstrap_values=bootstrap_values.cpu().numpy(),
        episodes_finished=episodes_finished,
        wins=wins,
        losses=losses,
        draws=draws,
        strategy_teacher_actions=strategy_teacher_actions,
    )
    return (
        rollout,
        (recurrent_state[0].detach(), recurrent_state[1].detach()),
        previous_actions,
        previous_rewards,
        episode_starts,
        (
            None
            if opponent_recurrent_state is None
            else (
                opponent_recurrent_state[0].detach(),
                opponent_recurrent_state[1].detach(),
            )
        ),
        opponent_previous_actions,
        opponent_previous_rewards,
        opponent_episode_starts,
    )


@torch.no_grad()
def _truncated_bootstrap(model, env, seats, indices, state, actions, builder, device):
    observations = [
        env.get_structured_observation(
            seat, actor_observation_domain=model.config.actor_observation_domain
        )
        for seat in seats
    ]
    masks = np.stack(
        [
            env.get_action_mask(
                seat,
                actor_observation_domain=model.config.actor_observation_domain,
                structured_observation=obs,
            )
            for seat, obs in zip(seats, observations)
        ]
    )
    inputs = _stack_step_inputs(
        observations,
        masks,
        actions[indices],
        np.zeros(len(seats), dtype=np.float32),
        np.zeros(len(seats), dtype=np.bool_),
        device,
        public_observation_confidence=model.config.public_observation_confidence,
        builder=builder,
    )
    selected = torch.as_tensor(indices, dtype=torch.long, device=device)
    next_state = tuple(value.index_select(0, selected) for value in state)
    return model(inputs, next_state).values[:, 0].cpu().numpy()


def _inputs_to_device(inputs: PolicyInputs, device: torch.device) -> PolicyInputs:
    if device.type == "cpu":
        return inputs
    return PolicyInputs(
        **{
            field.name: None
            if getattr(inputs, field.name) is None
            else getattr(inputs, field.name).to(device)
            for field in fields(PolicyInputs)
        }
    )


@torch.no_grad()
def _truncated_bootstrap_from_observation(
    model, observation, mask, index, state, actions, builder, device
):
    """``_truncated_bootstrap`` for one learner seat whose terminal observation
    was captured by an actor process before its environment reset."""
    inputs = _stack_step_inputs(
        [observation],
        np.stack([mask]),
        actions[np.asarray([index])],
        np.zeros(1, dtype=np.float32),
        np.zeros(1, dtype=np.bool_),
        device,
        public_observation_confidence=model.config.public_observation_confidence,
        builder=builder,
    )
    selected = torch.as_tensor([index], dtype=torch.long, device=device)
    next_state = tuple(value.index_select(0, selected) for value in state)
    return model(inputs, next_state).values[:, 0].cpu().numpy()


@_rollout_grad_mode
def collect_rollout_learner_inference(
    *,
    backend: Any,
    builder: StructuredObservationBuilder,
    model: ClasherPolicy,
    device: torch.device,
    rollout_steps: int,
    carry: dict[str, Any],
    policy_version: int,
    learner_decisions: int,
    state_dict: Any,
    quiet_engine: bool,
    hazard_conditioned_rollouts: bool = False,
    recurrent_update_mode: str = "full-prefix",
    tbptt_burn_in: int = 16,
) -> tuple[RolloutBatch, dict[str, Any]]:
    """Learner half of ``collect_rollout_stationary_opponents`` over a backend.

    The backend (actor processes or in-process environments) returns learner
    observations and masks and applies opponent actions and simulator steps in
    global environment order. This function performs every learner-side step of
    the admitted collector in the same order: exact prefix reconstruction,
    observation storage, one batched ``model.act`` over all environments with the
    learner Torch RNG, truncation bootstraps with the post-action state, and the
    final bootstrap value. Inputs are stacked on the CPU (also the history copy)
    and then moved to ``device``.
    """
    from .tbptt import RolloutStateRecorder, validate_mode

    validate_mode(recurrent_update_mode, 1, tbptt_burn_in)
    model.eval()
    causal_actor = (
        model.config.public_contract_version >= 4
        or model.config.actor_observation_domain
        in {
            "causal-vision-v1",
            "causal-frame-v1",
        }
    )
    recurrent_state = carry["recurrent_state"]
    previous_actions = carry["previous_actions"]
    previous_rewards = carry["previous_rewards"]
    episode_starts = carry["episode_starts"]
    history = carry.get("history")
    if causal_actor:
        previous_rewards = np.zeros_like(previous_rewards, dtype=np.float32)
    agents = backend.num_envs
    if model.config.public_contract_version >= 4 and backend.public_contract_versions != {
        model.config.public_contract_version
    }:
        raise ValueError(
            "council collection requires matching public environment contracts"
        )
    builder.public_contract_version = model.config.public_contract_version
    observations, action_masks_list = backend.begin(
        policy_version=policy_version,
        learner_decisions=learner_decisions,
        state_dict=state_dict,
    )
    num_actions = int(action_masks_list[0].shape[-1])
    no_op = num_actions - 2
    arrays = _empty_rollout_arrays(
        agents=agents,
        steps=rollout_steps,
        builder=builder,
        num_actions=num_actions,
    )
    recurrent_prefixes = None
    if model.config.public_contract_version >= 4 and recurrent_update_mode == "full-prefix":
        from .council_recurrence import RecurrentHistory, reconstruct_recurrent_state

        if history is None:
            history = RecurrentHistory(agents)
        recurrent_prefixes = history.snapshot()
        recurrent_state = reconstruct_recurrent_state(
            model,
            recurrent_prefixes,
            device=device,
        )
    recorder = (RolloutStateRecorder(model, recurrent_state, rollout_steps, tbptt_burn_in)
                if recurrent_update_mode == "stored-state" else None)
    initial_hidden = recurrent_state[0].detach().cpu().numpy().copy()
    initial_cell = recurrent_state[1].detach().cpu().numpy().copy()
    episodes_finished = wins = losses = draws = 0
    cpu = torch.device("cpu")

    for step in range(rollout_steps):
        action_masks = np.stack(action_masks_list)
        _store_observations(
            arrays,
            observations,
            action_masks,
            previous_actions,
            previous_rewards,
            episode_starts,
            step,
            builder=builder,
        )
        inputs = _stack_step_inputs(
            observations,
            action_masks,
            previous_actions,
            previous_rewards,
            episode_starts,
            cpu,
            public_observation_confidence=model.config.public_observation_confidence,
            builder=builder,
        )
        if recorder is not None:
            recorder.append(inputs, recurrent_state, step)
        if history is not None:
            history.append(inputs)
        actions_t, log_probs_t, values_t, recurrent_state, _ = model.act(
            _inputs_to_device(inputs, device),
            recurrent_state,
            deterministic=False,
            hazard_conditioned_stochastic=hazard_conditioned_rollouts,
        )
        actions = actions_t[:, 0].cpu().numpy().astype(np.int64, copy=False)
        arrays["actions"][:, step] = actions
        arrays["old_log_probs"][:, step] = log_probs_t[:, 0].cpu().numpy()
        arrays["old_values"][:, step] = values_t[:, 0].cpu().numpy()

        results, observations, action_masks_list = backend.step(actions)
        next_previous_actions = actions.copy()
        next_previous_rewards = np.zeros((agents,), dtype=np.float32)
        next_episode_starts = np.zeros((agents,), dtype=np.bool_)
        for env_index, result in enumerate(results):
            arrays["rewards"][env_index, step] = result.reward
            arrays["dones"][env_index, step] = result.done
            arrays["action_success"][env_index, step] = result.action_success
            if not causal_actor:
                next_previous_rewards[env_index] = result.reward
            if (
                result.truncation_observation is not None
                and model.config.public_contract_version >= 4
            ):
                arrays["truncation_bootstrap_values"][[env_index], step] = (
                    _truncated_bootstrap_from_observation(
                        model,
                        result.truncation_observation,
                        result.truncation_mask,
                        env_index,
                        recurrent_state,
                        actions,
                        builder,
                        device,
                    )
                )
            if result.done:
                episodes_finished += 1
                if result.learner_result == "draw":
                    draws += 1
                elif result.learner_result == "win":
                    wins += 1
                else:
                    losses += 1
                next_previous_actions[env_index] = no_op
                next_previous_rewards[env_index] = 0.0
                next_episode_starts[env_index] = True
        previous_actions = next_previous_actions
        previous_rewards = next_previous_rewards
        episode_starts = next_episode_starts

    bootstrap_inputs = _stack_step_inputs(
        observations,
        np.stack(action_masks_list),
        previous_actions,
        previous_rewards,
        episode_starts,
        device,
        public_observation_confidence=model.config.public_observation_confidence,
        builder=builder,
    )
    bootstrap_values = model.forward(bootstrap_inputs, recurrent_state).values[:, 0]
    rollout = RolloutBatch(
        **arrays,
        **(recorder.payload() if recorder is not None else {}),
        recurrent_prefixes=recurrent_prefixes,
        initial_hidden=initial_hidden,
        initial_cell=initial_cell,
        bootstrap_values=bootstrap_values.cpu().numpy(),
        episodes_finished=episodes_finished,
        wins=wins,
        losses=losses,
        draws=draws,
    )
    return rollout, {
        "recurrent_state": (recurrent_state[0].detach(), recurrent_state[1].detach()),
        "previous_actions": previous_actions,
        "previous_rewards": previous_rewards,
        "episode_starts": episode_starts,
        "history": history,
    }


def compute_gae(
    rollout: RolloutBatch,
    *,
    gamma: float,
    gae_lambda: float,
) -> tuple[np.ndarray, np.ndarray]:
    advantages = np.zeros_like(rollout.rewards, dtype=np.float32)
    last_gae = np.zeros((rollout.num_sequences,), dtype=np.float32)
    next_values = rollout.bootstrap_values.astype(np.float32, copy=True)
    for step in range(rollout.sequence_length - 1, -1, -1):
        non_terminal = 1.0 - rollout.dones[:, step].astype(np.float32)
        delta = (
            rollout.rewards[:, step]
            + gamma * next_values * non_terminal
            - rollout.old_values[:, step]
        )
        truncation_values = getattr(rollout, "truncation_bootstrap_values", None)
        if truncation_values is not None:
            delta += gamma * truncation_values[:, step]
        last_gae = delta + gamma * gae_lambda * non_terminal * last_gae
        advantages[:, step] = last_gae
        next_values = rollout.old_values[:, step]
    return advantages, advantages + rollout.old_values


def _sequence_inputs(
    rollout: RolloutBatch,
    indices: np.ndarray | slice,
    device: torch.device,
) -> PolicyInputs:
    def tensor(name: str, dtype: torch.dtype) -> Tensor:
        return torch.as_tensor(
            getattr(rollout, name)[indices], dtype=dtype, device=device
        )

    return PolicyInputs(
        entity_levels=None
        if rollout.entity_levels is None
        else tensor("entity_levels", torch.long),
        entity_level_confidence=None
        if rollout.entity_level_confidence is None
        else tensor("entity_level_confidence", torch.float32),
        hand_levels=None
        if rollout.hand_levels is None
        else tensor("hand_levels", torch.long),
        hand_level_confidence=None
        if rollout.hand_level_confidence is None
        else tensor("hand_level_confidence", torch.float32),
        own_last_play_ids=None
        if rollout.own_last_play_ids is None
        else tensor("own_last_play_ids", torch.long),
        own_last_play_features=None
        if rollout.own_last_play_features is None
        else tensor("own_last_play_features", torch.float32),
        entity_ids=tensor("entity_ids", torch.long),
        entity_features=tensor("entity_features", torch.float32),
        entity_mask=tensor("entity_mask", torch.bool),
        hand_ids=tensor("hand_ids", torch.long),
        global_features=tensor("global_features", torch.float32),
        opponent_history_ids=tensor("opponent_history_ids", torch.long),
        opponent_history_ages=tensor("opponent_history_ages", torch.float32),
        opponent_seen_card_ids=tensor("opponent_seen_card_ids", torch.long),
        opponent_play_event_ids=tensor("opponent_play_event_ids", torch.long),
        opponent_play_event_confidence=tensor(
            "opponent_play_event_confidence", torch.float32
        ),
        action_mask=tensor("action_masks", torch.bool),
        previous_actions=tensor("previous_actions", torch.long),
        previous_rewards=tensor("previous_rewards", torch.float32),
        episode_starts=tensor("episode_starts", torch.bool),
        entity_id_confidence=tensor("entity_id_confidence", torch.float32),
        entity_feature_confidence=tensor("entity_feature_confidence", torch.float32),
        hand_id_confidence=tensor("hand_id_confidence", torch.float32),
        global_feature_confidence=tensor("global_feature_confidence", torch.float32),
        critic_entity_ids=tensor("critic_entity_ids", torch.long),
        critic_entity_features=tensor("critic_entity_features", torch.float32),
        critic_entity_mask=tensor("critic_entity_mask", torch.bool),
        critic_card_ids=tensor("critic_card_ids", torch.long),
        critic_global_features=tensor("critic_global_features", torch.float32),
    )


def _index_policy_inputs(inputs: PolicyInputs, indices: Tensor) -> PolicyInputs:
    def select(value: Tensor | None) -> Tensor | None:
        return None if value is None else value.index_select(0, indices)

    return PolicyInputs(
        entity_levels=select(inputs.entity_levels),
        entity_level_confidence=select(inputs.entity_level_confidence),
        hand_levels=select(inputs.hand_levels),
        hand_level_confidence=select(inputs.hand_level_confidence),
        own_last_play_ids=select(inputs.own_last_play_ids),
        own_last_play_features=select(inputs.own_last_play_features),
        entity_ids=inputs.entity_ids.index_select(0, indices),
        entity_features=inputs.entity_features.index_select(0, indices),
        entity_mask=inputs.entity_mask.index_select(0, indices),
        hand_ids=inputs.hand_ids.index_select(0, indices),
        global_features=inputs.global_features.index_select(0, indices),
        opponent_history_ids=select(inputs.opponent_history_ids),
        opponent_history_ages=select(inputs.opponent_history_ages),
        opponent_seen_card_ids=select(inputs.opponent_seen_card_ids),
        opponent_play_event_ids=select(inputs.opponent_play_event_ids),
        opponent_play_event_confidence=select(inputs.opponent_play_event_confidence),
        action_mask=inputs.action_mask.index_select(0, indices),
        previous_actions=inputs.previous_actions.index_select(0, indices),
        previous_rewards=inputs.previous_rewards.index_select(0, indices),
        episode_starts=inputs.episode_starts.index_select(0, indices),
        entity_id_confidence=select(inputs.entity_id_confidence),
        entity_feature_confidence=select(inputs.entity_feature_confidence),
        hand_id_confidence=select(inputs.hand_id_confidence),
        global_feature_confidence=select(inputs.global_feature_confidence),
        critic_entity_ids=select(inputs.critic_entity_ids),
        critic_entity_features=select(inputs.critic_entity_features),
        critic_entity_mask=select(inputs.critic_entity_mask),
        critic_card_ids=select(inputs.critic_card_ids),
        critic_global_features=select(inputs.critic_global_features),
    )


def _opponent_hand_targets(card_ids: Tensor, num_tokens: int) -> Tensor:
    # Privileged card layout is [own hand+next, enemy hand+next]. Only the
    # four current enemy hand cards are targets for the belief auxiliary.
    enemy_hand = card_ids[..., 5:9]
    targets = torch.zeros(
        (*enemy_hand.shape[:-1], num_tokens),
        dtype=torch.float32,
        device=enemy_hand.device,
    )
    valid = enemy_hand != 0
    targets.scatter_add_(-1, enemy_hand, valid.to(torch.float32))
    targets[..., 0] = 0.0
    return targets.clamp_(0.0, 1.0)


def parameter_anchor_l2(
    model: ClasherPolicy,
    anchor_parameters: tuple[Tensor | None, ...],
) -> Tensor:
    """Half squared distance over parameters shared with a frozen anchor.

    A ``None`` entry denotes a parameter introduced by a zero-output architecture
    upgrade.  Such parameters have no corresponding value in the source checkpoint
    and must not be pulled toward an unrelated random initialization.
    """
    parameters = tuple(model.parameters())
    if len(parameters) != len(anchor_parameters):
        raise ValueError("anchor parameter count does not match model")
    penalty = torch.zeros((), dtype=parameters[0].dtype, device=parameters[0].device)
    for parameter, anchor in zip(parameters, anchor_parameters, strict=True):
        if anchor is None:
            continue
        if parameter.shape != anchor.shape:
            raise ValueError("anchor parameter shape does not match model")
        penalty = penalty + 0.5 * (parameter - anchor).square().sum()
    return penalty


def policy_anchor_kl(
    current_joint_logits: Tensor,
    anchor_joint_logits: Tensor,
    *,
    temperature: float = 1.0,
) -> Tensor:
    """Mean forward KL from a frozen anchor policy to the current policy."""
    if current_joint_logits.shape != anchor_joint_logits.shape:
        raise ValueError("anchor and current policy logits must have matching shapes")
    if not math.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("policy temperature must be finite and positive")
    current_log_prob = torch.log_softmax(current_joint_logits / temperature, dim=-1)
    anchor_log_prob = torch.log_softmax(anchor_joint_logits / temperature, dim=-1)
    anchor_prob = anchor_log_prob.exp()
    return (anchor_prob * (anchor_log_prob - current_log_prob)).sum(dim=-1).mean()


def factorized_policy_anchor_kl(
    current: PolicyOutput,
    anchor: PolicyOutput,
    action_mask: Tensor,
    *,
    component: Literal["joint", "location", "type"],
) -> Tensor:
    """Preserve a frozen policy at the requested factorized decision level.

    Joint KL is the historical behavior. Location KL compares the conditional
    tile distribution independently for every playable hand slot, preventing
    spatial drift from being diluted by card/no-op choice. Type KL preserves
    slot/no-op/ability choice while allowing placement geometry to move.
    """

    if component == "joint":
        return policy_anchor_kl(current.joint_logits, anchor.joint_logits)
    if component not in {"location", "type"}:
        raise ValueError("anchor component must be joint, location, or type")
    if current.joint_logits.shape != anchor.joint_logits.shape:
        raise ValueError("anchor and current policy logits must have matching shapes")
    if action_mask.shape != current.joint_logits.shape:
        raise ValueError("action mask shape must match policy logits")

    placement_mask = action_mask[..., :PLACEMENT_ACTIONS].reshape(
        *action_mask.shape[:-1], 4, -1
    )
    if component == "location":
        current_logits = current.location_logits
        anchor_logits = anchor.location_logits
        mask = placement_mask
    else:
        slot_mask = placement_mask.any(dim=-1)
        mask = torch.cat([slot_mask, action_mask[..., PLACEMENT_ACTIONS:]], dim=-1)
        current_logits = current.action_type_logits
        anchor_logits = anchor.action_type_logits
    if (
        current_logits.shape != anchor_logits.shape
        or mask.shape != current_logits.shape
    ):
        raise ValueError("factorized anchor logits and mask must have matching shapes")

    valid = mask.count_nonzero(dim=-1) > 1
    if not bool(valid.any()):
        return current_logits.sum() * 0.0
    current_log_prob = torch.log_softmax(
        current_logits.masked_fill(~mask, -1e9), dim=-1
    )
    anchor_log_prob = torch.log_softmax(anchor_logits.masked_fill(~mask, -1e9), dim=-1)
    anchor_prob = anchor_log_prob.exp()
    per_decision = (anchor_prob * (anchor_log_prob - current_log_prob)).sum(dim=-1)
    return per_decision[valid].mean()


def online_strategy_teacher_loss(
    output: PolicyOutput,
    action_mask: Tensor,
    teacher_actions: Tensor,
    *,
    decision_coef: float,
    card_coef: float,
    tile_coef: float,
    play_weight: float,
) -> dict[str, Tensor]:
    """Supervise timing, card, and tile independently on learner states."""

    expected_actions = PLACEMENT_ACTIONS + 2
    if action_mask.shape != (*teacher_actions.shape, expected_actions):
        raise ValueError("online teacher action-mask shape differs")
    if action_mask.dtype != torch.bool or teacher_actions.dtype != torch.long:
        raise ValueError("online teacher mask/actions have invalid dtypes")
    flat_actions = teacher_actions.reshape(-1)
    flat_mask = action_mask.reshape(-1, expected_actions)
    if bool(
        ((flat_actions < 0) | (flat_actions >= expected_actions)).any()
    ):
        raise ValueError("online teacher action is outside the action space")
    if not bool(flat_mask.gather(1, flat_actions[:, None]).all()):
        raise ValueError("online teacher emitted a non-public-legal action")

    type_logits = output.action_type_logits.reshape(-1, NUM_HAND_SLOTS + 2)
    tile_logits = output.location_logits.reshape(
        -1, NUM_HAND_SLOTS, NUM_TILES
    )
    placement_mask = flat_mask[:, :PLACEMENT_ACTIONS].reshape(
        -1, NUM_HAND_SLOTS, NUM_TILES
    )
    card_mask = placement_mask.any(dim=-1)
    decision_mask = torch.stack(
        (
            card_mask.any(dim=-1),
            flat_mask[:, PLACEMENT_ACTIONS],
            flat_mask[:, PLACEMENT_ACTIONS + 1],
        ),
        dim=-1,
    )
    masked_card_logits = type_logits[:, :NUM_HAND_SLOTS].masked_fill(
        ~card_mask, -1e9
    )
    decision_logits = torch.stack(
        (
            torch.logsumexp(masked_card_logits, dim=-1),
            type_logits[:, NUM_HAND_SLOTS],
            type_logits[:, NUM_HAND_SLOTS + 1],
        ),
        dim=-1,
    ).masked_fill(~decision_mask, -1e9)
    placement = flat_actions < PLACEMENT_ACTIONS
    decision_targets = torch.where(
        placement,
        torch.zeros_like(flat_actions),
        torch.where(
            flat_actions == PLACEMENT_ACTIONS,
            torch.ones_like(flat_actions),
            torch.full_like(flat_actions, 2),
        ),
    )
    decision_weights = torch.where(
        placement,
        torch.full_like(flat_actions, play_weight, dtype=torch.float32),
        torch.ones_like(flat_actions, dtype=torch.float32),
    )
    decision_per_row = F.cross_entropy(
        decision_logits, decision_targets, reduction="none"
    )
    decision_loss = (decision_per_row * decision_weights).sum() / (
        decision_weights.sum().clamp_min(1.0)
    )

    placement_rows = torch.nonzero(placement, as_tuple=False).flatten()
    if placement_rows.numel():
        placement_actions = flat_actions.index_select(0, placement_rows)
        card_targets = torch.div(
            placement_actions, NUM_TILES, rounding_mode="floor"
        )
        tile_targets = placement_actions.remainder(NUM_TILES)
        selected_card_logits = masked_card_logits.index_select(0, placement_rows)
        card_loss = F.cross_entropy(selected_card_logits, card_targets)
        row_indices = torch.arange(
            placement_rows.numel(), device=flat_actions.device
        )
        selected_tile_logits = tile_logits.index_select(0, placement_rows)[
            row_indices, card_targets
        ]
        selected_tile_mask = placement_mask.index_select(0, placement_rows)[
            row_indices, card_targets
        ]
        tile_loss = F.cross_entropy(
            selected_tile_logits.masked_fill(~selected_tile_mask, -1e9),
            tile_targets,
        )
        card_accuracy = (
            selected_card_logits.argmax(dim=-1) == card_targets
        ).float().mean()
        tile_accuracy = (
            selected_tile_logits.masked_fill(~selected_tile_mask, -1e9).argmax(
                dim=-1
            )
            == tile_targets
        ).float().mean()
    else:
        card_loss = masked_card_logits.sum() * 0.0
        tile_loss = tile_logits.sum() * 0.0
        card_accuracy = card_loss.detach()
        tile_accuracy = tile_loss.detach()
    decision_predictions = decision_logits.argmax(dim=-1)
    decision_accuracy = (decision_predictions == decision_targets).float().mean()
    play_recall = (
        (decision_predictions[placement] == 0).float().mean()
        if placement_rows.numel()
        else decision_accuracy.detach() * 0.0
    )
    total = (
        decision_coef * decision_loss
        + card_coef * card_loss
        + tile_coef * tile_loss
    )
    return {
        "loss": total,
        "decision_loss": decision_loss,
        "card_loss": card_loss,
        "tile_loss": tile_loss,
        "decision_accuracy": decision_accuracy,
        "play_recall": play_recall,
        "card_accuracy": card_accuracy,
        "tile_accuracy": tile_accuracy,
        "play_rate": placement.float().mean(),
    }


def ppo_update(
    *,
    model: ClasherPolicy,
    optimizer: torch.optim.Optimizer,
    rollout: RolloutBatch,
    advantages: np.ndarray,
    returns: np.ndarray,
    device: torch.device,
    epochs: int,
    sequence_batch_size: int,
    clip_ratio: float,
    value_coef: float,
    entropy_coef: float,
    hand_aux_coef: float,
    elixir_aux_coef: float,
    target_kl: float,
    action_value_coef: float = 0.0,
    sampling_temperature: float = 1.0,
    action_type_entropy_coef: float | None = None,
    location_entropy_coef: float | None = None,
    conditional_slot_entropy_coef: float = 0.0,
    online_strategy_teacher_coef: float = 0.0,
    online_strategy_teacher_decision_coef: float = 1.0,
    online_strategy_teacher_card_coef: float = 1.0,
    online_strategy_teacher_tile_coef: float = 1.0,
    online_strategy_teacher_play_weight: float = 4.0,
    anchor_parameters: tuple[Tensor | None, ...] | None = None,
    anchor_l2_coef: float = 0.0,
    anchor_model: ClasherPolicy | None = None,
    anchor_policy_kl_coef: float = 0.0,
    rehearsal: PlacementRehearsal | None = None,
    rehearsal_coef: float = 0.0,
    rehearsal_batch_sequences: int = 1,
    causal_rehearsal: CausalDecisionRehearsal | None = None,
    causal_rehearsal_coef: float = 0.0,
    causal_rehearsal_decision_coef: float = 1.0,
    causal_rehearsal_decision_positive_weight: float | None = None,
    causal_rehearsal_card_coef: float = 0.0,
    causal_rehearsal_tile_coef: float = 0.0,
    causal_rehearsal_batch_sequences: int = 1,
    causal_spatial_rehearsal: CausalDecisionRehearsal | None = None,
    causal_spatial_rehearsal_coef: float = 0.0,
    causal_spatial_rehearsal_card_coef: float = 1.0,
    causal_spatial_rehearsal_tile_coef: float = 0.0,
    causal_spatial_rehearsal_batch_sequences: int = 1,
    anchor_rehearsal: PlacementRehearsal | None = None,
    anchor_rehearsal_coef: float = 0.0,
    anchor_rehearsal_batch_sequences: int = 1,
    hazard_conditioned_rollouts: bool = False,
    critic_only: bool = False,
    apply_optimizer_step: bool = True,
    recurrent_update_mode: str = "full-prefix",
    tbptt_chunk: int = 64,
    tbptt_burn_in: int = 16,
) -> dict[str, float]:
    """Run PPO epochs over one rollout.

    ``critic_only`` is the post-warm-start critic warm-up: the loss is the value
    loss alone and every parameter outside the separate critic encoder and
    value head keeps a ``None`` gradient, so AdamW leaves it (and its optimizer
    state) bit-identical.

    ``apply_optimizer_step=False`` is the launch preflight: every loss, backward
    and gradient check runs, ``optimizer.step()`` is never called, and gradients
    are cleared afterward, so weights and optimizer state stay bit-identical.
    """
    from .tbptt import validate_mode, chunk_minibatches, select_steps, rollout_chunk_state, trim_entity_padding

    validate_mode(recurrent_update_mode, tbptt_chunk, tbptt_burn_in)
    if not math.isfinite(sampling_temperature) or sampling_temperature <= 0.0:
        raise ValueError("sampling temperature must be finite and positive")
    critic_names = critic_parameter_names(model) if critic_only else frozenset()
    if not math.isfinite(action_value_coef) or action_value_coef < 0.0:
        raise ValueError("action value coefficient must be finite and nonnegative")
    model.train()
    normalized_advantages = (advantages - float(advantages.mean())) / (
        float(advantages.std()) + 1e-8
    )
    stat_sums = {
        "loss": 0.0,
        "policy_loss": 0.0,
        "value_loss": 0.0,
        "action_value_loss": 0.0,
        "action_value_policy_gate": 0.0,
        "entropy": 0.0,
        "action_type_entropy": 0.0,
        "location_entropy": 0.0,
        "conditional_slot_entropy": 0.0,
        "mode_entropy": 0.0,
        "anchor_l2": 0.0,
        "anchor_loss": 0.0,
        "anchor_policy_kl": 0.0,
        "anchor_policy_kl_loss": 0.0,
        "rehearsal_loss": 0.0,
        "rehearsal_weighted_loss": 0.0,
        "causal_rehearsal_loss": 0.0,
        "causal_rehearsal_weighted_loss": 0.0,
        "causal_spatial_rehearsal_loss": 0.0,
        "causal_spatial_rehearsal_weighted_loss": 0.0,
        "anchor_rehearsal_kl": 0.0,
        "anchor_rehearsal_loss": 0.0,
        "online_teacher_loss": 0.0,
        "online_teacher_weighted_loss": 0.0,
        "online_teacher_decision_loss": 0.0,
        "online_teacher_card_loss": 0.0,
        "online_teacher_tile_loss": 0.0,
        "online_teacher_decision_accuracy": 0.0,
        "online_teacher_play_recall": 0.0,
        "online_teacher_card_accuracy": 0.0,
        "online_teacher_tile_accuracy": 0.0,
        "online_teacher_play_rate": 0.0,
        "hand_loss": 0.0,
        "elixir_loss": 0.0,
        "approx_kl": 0.0,
        "clip_fraction": 0.0,
        "grad_norm": 0.0,
    }
    updates = 0
    stop_early = False
    positive_weight = torch.tensor(
        min(20.0, max(1.0, (model.config.num_tokens - 4) / 4)),
        dtype=torch.float32,
        device=device,
    )
    all_inputs = _sequence_inputs(rollout, slice(None), device)
    if model.config.public_observation_confidence:
        all_inputs = all_inputs.with_exact_actor_confidence()
    all_initial_hidden = torch.as_tensor(
        rollout.initial_hidden, dtype=torch.float32, device=device
    )
    all_initial_cell = torch.as_tensor(
        rollout.initial_cell, dtype=torch.float32, device=device
    )
    all_actions = torch.as_tensor(rollout.actions, dtype=torch.long, device=device)
    all_old_log_prob = torch.as_tensor(
        rollout.old_log_probs, dtype=torch.float32, device=device
    )
    all_old_values = torch.as_tensor(
        rollout.old_values, dtype=torch.float32, device=device
    )
    all_advantages = torch.as_tensor(
        normalized_advantages, dtype=torch.float32, device=device
    )
    all_returns = torch.as_tensor(returns, dtype=torch.float32, device=device)
    all_teacher_actions = (
        None
        if rollout.strategy_teacher_actions is None
        else torch.as_tensor(
            rollout.strategy_teacher_actions,
            dtype=torch.long,
            device=device,
        )
    )
    if (all_teacher_actions is None) != (online_strategy_teacher_coef == 0.0):
        raise ValueError(
            "online teacher rollout labels and a positive coefficient are "
            "required together"
        )

    for _epoch in range(epochs):
        if recurrent_update_mode == "stored-state":
            minibatches = chunk_minibatches(rollout.episode_starts, tbptt_chunk, sequence_batch_size)
        else:
            order = np.random.permutation(rollout.num_sequences)
            minibatches = (order[start:start + sequence_batch_size]
                           for start in range(0, rollout.num_sequences, sequence_batch_size))
        for indices in minibatches:
            if recurrent_update_mode == "stored-state":
                rows = torch.tensor([item[0] for item in indices], device=device)[:, None]
                times = torch.tensor([list(range(item[1], item[2])) for item in indices], device=device)
                inputs = trim_entity_padding(select_steps(all_inputs, rows, times))
                initial_state = rollout_chunk_state(model, rollout, all_inputs, indices,
                                                    tbptt_burn_in, device=device)
                def select(value):
                    return value[rows, times]
            else:
                index_tensor = torch.as_tensor(indices, dtype=torch.long, device=device)
                inputs = _index_policy_inputs(all_inputs, index_tensor)
                initial_state = (
                    all_initial_hidden.index_select(0, index_tensor),
                    all_initial_cell.index_select(0, index_tensor),
                )
                if model.config.public_contract_version >= 4:
                    from .council_recurrence import reconstruct_recurrent_state

                    if rollout.recurrent_prefixes is None:
                        raise ValueError("council PPO requires retained episode prefixes")
                    initial_state = reconstruct_recurrent_state(
                        model,
                        tuple(rollout.recurrent_prefixes[int(index)] for index in indices),
                        device=device,
                    )
                def select(value):
                    return value.index_select(0, index_tensor)
            output = model(inputs, initial_state)
            actions = select(all_actions)
            force_play: Tensor | None = None
            if model.config.play_hazard_enabled:
                # The hard recurrent hazard gate is part of the behavior state
                # that generated this rollout.  Recomputing it after an optimizer
                # step can flip support and make a stored legal action have
                # probability zero.  Gated collection guarantees placement iff
                # the behavior gate fired, so the stored action exactly recovers
                # that discrete conditioning variable for PPO ratio evaluation.
                force_play = actions < PLACEMENT_ACTIONS
            distribution = output.distribution(
                temperature=sampling_temperature,
                force_play=force_play,
            )
            old_log_prob = select(all_old_log_prob)
            old_values = select(all_old_values)
            advantage = select(all_advantages)
            return_target = select(all_returns)

            new_log_prob = distribution.log_prob(actions)
            log_ratio = new_log_prob - old_log_prob
            ratio = log_ratio.exp()
            unclipped = ratio * advantage
            clipped = torch.clamp(ratio, 1.0 - clip_ratio, 1.0 + clip_ratio) * advantage
            policy_loss = -torch.minimum(unclipped, clipped).mean()

            value_delta = output.values - old_values
            clipped_values = old_values + value_delta.clamp(-clip_ratio, clip_ratio)
            value_loss_unclipped = (output.values - return_target).square()
            value_loss_clipped = (clipped_values - return_target).square()
            value_loss = (
                0.5 * torch.maximum(value_loss_unclipped, value_loss_clipped).mean()
            )
            if output.action_values is None:
                if action_value_coef > 0.0:
                    raise ValueError(
                        "positive action-value coefficient requires the action-value head"
                    )
                action_value_loss = output.values.sum() * 0.0
                action_value_policy_gate = output.values.sum() * 0.0
            else:
                selected_action_values = output.action_values.gather(
                    -1, actions.unsqueeze(-1)
                ).squeeze(-1)
                action_value_loss = F.smooth_l1_loss(
                    selected_action_values,
                    return_target.detach(),
                )
                assert model.action_value_policy_gate is not None
                action_value_policy_gate = torch.tanh(
                    model.action_value_policy_gate
                )
            entropy = distribution.entropy().mean()
            action_type_entropy, location_entropy = output.entropy_components(
                temperature=sampling_temperature,
                force_play=force_play,
            )
            action_type_entropy = action_type_entropy.mean()
            location_entropy = location_entropy.mean()
            conditional_slot_entropy = output.conditional_slot_entropy(
                temperature=sampling_temperature,
                force_play=force_play,
            ).mean()
            mode_probabilities = torch.cat(
                (
                    distribution.probs[..., :PLACEMENT_ACTIONS].sum(-1, keepdim=True),
                    distribution.probs[..., PLACEMENT_ACTIONS:],
                ),
                dim=-1,
            )
            mode_entropy = (
                -(mode_probabilities * mode_probabilities.clamp_min(1e-30).log())
                .sum(-1)
                .mean()
            )

            assert inputs.critic_card_ids is not None
            assert inputs.critic_global_features is not None
            hand_targets = _opponent_hand_targets(
                inputs.critic_card_ids, model.config.num_tokens
            )
            hand_loss = F.binary_cross_entropy_with_logits(
                output.opponent_hand_logits,
                hand_targets,
                pos_weight=positive_weight,
            )
            enemy_elixir_target = inputs.critic_global_features[..., -2]
            elixir_loss = F.smooth_l1_loss(output.opponent_elixir, enemy_elixir_target)
            if action_type_entropy_coef is None and location_entropy_coef is None:
                entropy_bonus = entropy_coef * entropy
            else:
                effective_type_coef = (
                    entropy_coef
                    if action_type_entropy_coef is None
                    else action_type_entropy_coef
                )
                effective_location_coef = (
                    entropy_coef
                    if location_entropy_coef is None
                    else location_entropy_coef
                )
                entropy_bonus = (
                    effective_type_coef * action_type_entropy
                    + effective_location_coef * location_entropy
                )
            entropy_bonus = (
                entropy_bonus + conditional_slot_entropy_coef * conditional_slot_entropy
            )
            anchor_l2 = (
                parameter_anchor_l2(model, anchor_parameters)
                if anchor_parameters is not None
                else torch.zeros((), dtype=output.values.dtype, device=device)
            )
            anchor_loss = anchor_l2_coef * anchor_l2
            if anchor_model is None:
                anchor_policy_kl = torch.zeros(
                    (), dtype=output.values.dtype, device=device
                )
            else:
                with torch.no_grad():
                    anchor_output = anchor_model(inputs, initial_state)
                    anchor_distribution = anchor_output.distribution(
                        temperature=sampling_temperature,
                        force_play=force_play,
                    )
                anchor_policy_kl = policy_anchor_kl(
                    distribution.logits,
                    anchor_distribution.logits,
                )
                if model.config.play_hazard_enabled:
                    if (
                        output.play_hazard_logits is None
                        or anchor_output.play_hazard_logits is None
                    ):
                        raise ValueError(
                            "hazard-enabled anchor policies must emit hazard logits"
                        )
                    anchor_hazard_prob = torch.sigmoid(
                        anchor_output.play_hazard_logits
                        - math.log(anchor_model.config.play_hazard_positive_weight)
                    )
                    current_hazard_logits = (
                        output.play_hazard_logits
                        - math.log(model.config.play_hazard_positive_weight)
                    )
                    hazard_cross_entropy = F.binary_cross_entropy_with_logits(
                        current_hazard_logits,
                        anchor_hazard_prob,
                    )
                    hazard_entropy = F.binary_cross_entropy(
                        anchor_hazard_prob,
                        anchor_hazard_prob,
                    )
                    anchor_policy_kl = (
                        anchor_policy_kl
                        + hazard_cross_entropy
                        - hazard_entropy
                    )
            anchor_policy_kl_loss = anchor_policy_kl_coef * anchor_policy_kl
            if rehearsal is None:
                rehearsal_loss = torch.zeros(
                    (), dtype=output.values.dtype, device=device
                )
            else:
                rehearsal_loss = rehearsal.loss(
                    model,
                    device=device,
                    batch_sequences=rehearsal_batch_sequences,
                )
            rehearsal_weighted_loss = rehearsal_coef * rehearsal_loss
            if causal_rehearsal is None:
                causal_rehearsal_loss = torch.zeros(
                    (), dtype=output.values.dtype, device=device
                )
            else:
                causal_rehearsal_loss = causal_rehearsal.loss(
                    model,
                    device=device,
                    batch_sequences=causal_rehearsal_batch_sequences,
                    decision_loss_coef=causal_rehearsal_decision_coef,
                    decision_positive_weight=(
                        causal_rehearsal_decision_positive_weight
                    ),
                    card_loss_coef=causal_rehearsal_card_coef,
                    tile_loss_coef=causal_rehearsal_tile_coef,
                )
            causal_rehearsal_weighted_loss = (
                causal_rehearsal_coef * causal_rehearsal_loss
            )
            if causal_spatial_rehearsal is None:
                causal_spatial_rehearsal_loss = torch.zeros(
                    (), dtype=output.values.dtype, device=device
                )
            else:
                causal_spatial_rehearsal_loss = causal_spatial_rehearsal.loss(
                    model,
                    device=device,
                    batch_sequences=causal_spatial_rehearsal_batch_sequences,
                    decision_loss_coef=0.0,
                    card_loss_coef=causal_spatial_rehearsal_card_coef,
                    tile_loss_coef=causal_spatial_rehearsal_tile_coef,
                )
            causal_spatial_rehearsal_weighted_loss = (
                causal_spatial_rehearsal_coef * causal_spatial_rehearsal_loss
            )
            if anchor_rehearsal is None:
                anchor_rehearsal_kl = torch.zeros(
                    (), dtype=output.values.dtype, device=device
                )
            else:
                if anchor_model is None:
                    raise ValueError("anchor rehearsal requires a frozen anchor model")
                anchor_rehearsal_kl = anchor_rehearsal.anchor_policy_kl(
                    model,
                    anchor_model,
                    device=device,
                    batch_sequences=anchor_rehearsal_batch_sequences,
                )
            anchor_rehearsal_loss = anchor_rehearsal_coef * anchor_rehearsal_kl
            if all_teacher_actions is None:
                online_teacher = {
                    name: torch.zeros(
                        (), dtype=output.values.dtype, device=device
                    )
                    for name in (
                        "loss",
                        "decision_loss",
                        "card_loss",
                        "tile_loss",
                        "decision_accuracy",
                        "play_recall",
                        "card_accuracy",
                        "tile_accuracy",
                        "play_rate",
                    )
                }
            else:
                online_teacher = online_strategy_teacher_loss(
                    output,
                    inputs.action_mask,
                    select(all_teacher_actions),
                    decision_coef=online_strategy_teacher_decision_coef,
                    card_coef=online_strategy_teacher_card_coef,
                    tile_coef=online_strategy_teacher_tile_coef,
                    play_weight=online_strategy_teacher_play_weight,
                )
            online_teacher_weighted_loss = (
                online_strategy_teacher_coef * online_teacher["loss"]
            )
            loss = (
                policy_loss
                + value_coef * value_loss
                + action_value_coef * action_value_loss
                - entropy_bonus
                + anchor_loss
                + anchor_policy_kl_loss
                + rehearsal_weighted_loss
                + causal_rehearsal_weighted_loss
                + causal_spatial_rehearsal_weighted_loss
                + anchor_rehearsal_loss
                + online_teacher_weighted_loss
                + hand_aux_coef * hand_loss
                + elixir_aux_coef * elixir_loss
            )
            if critic_only:
                loss = value_coef * value_loss

            if not bool(torch.isfinite(loss)):
                raise FloatingPointError(
                    "non-finite PPO loss before backward: "
                    f"policy={float(policy_loss.detach()):.9g} "
                    f"value={float(value_loss.detach()):.9g} "
                    f"entropy={float(entropy.detach()):.9g} "
                    f"anchor_l2={float(anchor_l2.detach()):.9g} "
                    f"anchor_kl={float(anchor_policy_kl.detach()):.9g} "
                    f"rehearsal={float(rehearsal_loss.detach()):.9g} "
                    "causal_rehearsal="
                    f"{float(causal_rehearsal_loss.detach()):.9g} "
                    "causal_spatial_rehearsal="
                    f"{float(causal_spatial_rehearsal_loss.detach()):.9g} "
                    "anchor_rehearsal_kl="
                    f"{float(anchor_rehearsal_kl.detach()):.9g}"
                    " online_teacher="
                    f"{float(online_teacher['loss'].detach()):.9g}"
                )

            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            if critic_only:
                for name, parameter in model.named_parameters():
                    if name not in critic_names:
                        parameter.grad = None
            nonfinite_gradients = [
                name
                for name, parameter in model.named_parameters()
                if parameter.grad is not None
                and not bool(torch.isfinite(parameter.grad).all())
            ]
            if nonfinite_gradients:
                raise FloatingPointError(
                    "non-finite PPO gradients: " + ", ".join(nonfinite_gradients)
                )
            grad_norm = nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            if not bool(torch.isfinite(grad_norm)):
                raise FloatingPointError(
                    f"non-finite PPO gradient norm: {float(grad_norm.detach()):.9g}"
                )
            if apply_optimizer_step:
                optimizer.step()
            nonfinite_parameters = [
                name
                for name, parameter in model.named_parameters()
                if not bool(torch.isfinite(parameter).all())
            ]
            if nonfinite_parameters:
                raise FloatingPointError(
                    "non-finite PPO parameters after optimizer step: "
                    + ", ".join(nonfinite_parameters)
                )

            with torch.no_grad():
                approx_kl = ((ratio - 1.0) - log_ratio).mean()
                clip_fraction = ((ratio - 1.0).abs() > clip_ratio).float().mean()
            values = {
                "loss": loss,
                "policy_loss": policy_loss,
                "value_loss": value_loss,
                "action_value_loss": action_value_loss,
                "action_value_policy_gate": action_value_policy_gate,
                "entropy": entropy,
                "action_type_entropy": action_type_entropy,
                "location_entropy": location_entropy,
                "conditional_slot_entropy": conditional_slot_entropy,
                "mode_entropy": mode_entropy,
                "anchor_l2": anchor_l2,
                "anchor_loss": anchor_loss,
                "anchor_policy_kl": anchor_policy_kl,
                "anchor_policy_kl_loss": anchor_policy_kl_loss,
                "rehearsal_loss": rehearsal_loss,
                "rehearsal_weighted_loss": rehearsal_weighted_loss,
                "causal_rehearsal_loss": causal_rehearsal_loss,
                "causal_rehearsal_weighted_loss": causal_rehearsal_weighted_loss,
                "causal_spatial_rehearsal_loss": causal_spatial_rehearsal_loss,
                "causal_spatial_rehearsal_weighted_loss": (
                    causal_spatial_rehearsal_weighted_loss
                ),
                "anchor_rehearsal_kl": anchor_rehearsal_kl,
                "anchor_rehearsal_loss": anchor_rehearsal_loss,
                "online_teacher_loss": online_teacher["loss"],
                "online_teacher_weighted_loss": online_teacher_weighted_loss,
                "online_teacher_decision_loss": online_teacher["decision_loss"],
                "online_teacher_card_loss": online_teacher["card_loss"],
                "online_teacher_tile_loss": online_teacher["tile_loss"],
                "online_teacher_decision_accuracy": online_teacher["decision_accuracy"],
                "online_teacher_play_recall": online_teacher["play_recall"],
                "online_teacher_card_accuracy": online_teacher["card_accuracy"],
                "online_teacher_tile_accuracy": online_teacher["tile_accuracy"],
                "online_teacher_play_rate": online_teacher["play_rate"],
                "hand_loss": hand_loss,
                "elixir_loss": elixir_loss,
                "approx_kl": approx_kl,
                "clip_fraction": clip_fraction,
                "grad_norm": grad_norm,
            }
            for key, value in values.items():
                stat_sums[key] += float(value.detach().cpu())
            updates += 1
            if target_kl > 0.0 and float(approx_kl) > target_kl:
                stop_early = True
                break
        if stop_early:
            break

    if not apply_optimizer_step:
        optimizer.zero_grad(set_to_none=True)
    if updates:
        for key in stat_sums:
            stat_sums[key] /= updates
    stat_sums["optimizer_steps"] = float(updates if apply_optimizer_step else 0)
    stat_sums["evaluated_minibatches"] = float(updates)
    stat_sums["kl_early_stop"] = float(stop_early)
    stat_sums["critic_warmup"] = float(critic_only)
    prediction = rollout.old_values.reshape(-1)
    target = returns.reshape(-1)
    variance = float(np.var(target))
    stat_sums["explained_variance"] = (
        float(1.0 - np.var(target - prediction) / variance) if variance > 1e-8 else 0.0
    )
    return stat_sums


CRITIC_PARAMETER_PREFIXES = ("critic_encoder.", "value_head.")


def critic_parameter_names(model: ClasherPolicy) -> frozenset[str]:
    """Parameters that only the privileged critic path owns."""
    names = frozenset(
        name
        for name, _ in model.named_parameters()
        if name.startswith(CRITIC_PARAMETER_PREFIXES)
    )
    if not any(name.startswith("value_head.") for name in names):
        raise ValueError("critic warm-up requires a separate value head")
    return names


def find_latest_checkpoint(directory: Path) -> Path | None:
    candidates = sorted(directory.glob("policy_v2_update_*.pt"))
    return candidates[-1] if candidates else None


def save_checkpoint(
    path: Path,
    *,
    model: ClasherPolicy,
    optimizer: torch.optim.Optimizer,
    builder: StructuredObservationBuilder,
    args: argparse.Namespace,
    update: int,
    total_transitions: int,
    metrics: dict[str, float] | None = None,
    simulation_backend_metadata: dict[str, Any] | None = None,
    council_initialization: dict[str, Any] | None = None,
) -> None:
    resource_budget = None
    if getattr(args, "council_budget_ledger", None) is not None:
        from .council_budget import budget_snapshot
        resource_budget = budget_snapshot(args.council_budget_ledger)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    torch.save(
        {
            "format_version": 2,
            "gamedata_sha256": _sha256(builder.loader.data_file),
            "council_config_sha256": (
                _sha256(args.council_config)
                if getattr(args, "council_config", None) is not None
                else None
            ),
            "admission_sha256": (
                _sha256(args.council_admission)
                if getattr(args, "council_admission", None) is not None
                else None
            ),
            "model_type": "entity_spatial_recurrent",
            "resource_budget": resource_budget,
            "council_recipe": (
                {
                    "arm": getattr(args, "council_arm", None),
                    "critic_warmup_updates": getattr(
                        args, "critic_warmup_updates", 0
                    ),
                    "target_kl": getattr(args, "target_kl", None),
                }
                if getattr(args, "council_config", None) is not None
                else None
            ),
            "model_config": model.config.to_dict(),
            "token_names": builder.token_names,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "args": vars(args),
            "update": update,
            "total_transitions": total_transitions,
            "metrics": metrics or {},
            "simulation_backend_metadata": simulation_backend_metadata,
            "council_initialization": council_initialization,
        },
        temporary,
    )
    os.replace(temporary, path)


def planned_rollout_steps(
    *,
    total_decisions: int,
    target_decisions: int | None,
    checkpoint_decisions: tuple[int, ...],
    agents: int,
    rollout_steps: int,
) -> int:
    """Shorten the final chunk so learner-decision milestones are exact."""
    if agents <= 0 or rollout_steps <= 0:
        raise ValueError("rollout dimensions must be positive")
    if target_decisions is None:
        return rollout_steps
    if total_decisions >= target_decisions:
        return 0
    boundary = min(
        [
            target_decisions,
            *(value for value in checkpoint_decisions if value > total_decisions),
        ]
    )
    remaining = boundary - total_decisions
    if remaining % agents:
        raise ValueError(
            "decision boundaries must be divisible by learner sequence count"
        )
    return min(rollout_steps, remaining // agents)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the recurrent entity-spatial policy with PPO self-play"
    )
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--council-config", type=Path)
    parser.add_argument("--council-admission", type=Path)
    parser.add_argument("--council-opponent-pool", type=Path)
    parser.add_argument("--council-budget-ledger", type=Path)
    parser.add_argument(
        "--simulation-backend",
        choices=("python", "simple-pytorch"),
        default="python",
        help="battle backend; simple-pytorch is a fresh-only dense tensor Gym",
    )
    parser.add_argument(
        "--simple-supported-decks-path",
        default="training_decks/simple_gym_supported_v1.json",
        help="fail-closed supported-deck artifact for --simulation-backend simple-pytorch",
    )
    parser.add_argument(
        "--simple-token-vocabulary-path",
        default="reports/current_client_youtube_stable_vocabulary_v1.json",
        help="typed current-client actor vocabulary for the simple PyTorch backend",
    )
    parser.add_argument(
        "--simple-max-entities",
        type=int,
        default=128,
        help="fresh Simple Gym entity/observation capacity; persisted in checkpoints",
    )
    parser.add_argument(
        "--simple-max-effects",
        type=int,
        default=128,
        help="fresh Simple Gym persistent-effect capacity; persisted in checkpoints",
    )
    parser.add_argument(
        "--simple-learner-sampling-temperature",
        type=float,
        default=1.0,
        help=(
            "stochastic learner-policy temperature for Simple Gym collection and "
            "the matching PPO behavior distribution"
        ),
    )
    parser.add_argument(
        "--simple-learner-deck-name",
        default="Hog 2.6 Cycle",
        help="exact supported-deck name assigned to every stationary learner row",
    )
    parser.add_argument(
        "--simple-checkpoint-opponent-deck-name",
        default=None,
        help=(
            "optional exact supported deck assigned to frozen checkpoint rows; "
            "use the learner deck for a true frozen-parent mirror"
        ),
    )
    parser.add_argument(
        "--public-contract-version", type=int, choices=(1, 2, 3, 4), default=1
    )
    parser.add_argument("--public-history-slots", type=int, default=0)
    parser.add_argument("--public-seen-card-slots", type=int, default=0)
    parser.add_argument(
        "--card-semantics-version",
        type=int,
        choices=(1, 2, 3, 4),
        default=1,
        help=(
            "public card descriptor schema for a fresh model; v2 replaces the "
            "legacy table, while v3 preserves it and adds a zero-initialized "
            "shared mechanics adapter; v4 corrects compact target flags and "
            "derives missing character mass without changing the v3 layout"
        ),
    )
    parser.add_argument(
        "--actor-observation-domain",
        choices=("simulator-exact", "causal-vision-v1", "causal-frame-v1"),
        default="simulator-exact",
        help=(
            "fresh-model actor domain; causal-frame-v1 additionally removes "
            "external temporal stabilization so private model state owns history"
        ),
    )
    parser.add_argument(
        "--sampling-decks-path",
        default=None,
        help=(
            "optional deck pool used only for training matchup sampling; "
            "--decks-path still defines the full observation vocabulary"
        ),
    )
    parser.add_argument(
        "--learner-sampling-decks-path",
        default=None,
        help="optional learner-only deck pool for stationary-opponent curricula",
    )
    parser.add_argument(
        "--opponent-sampling-decks-path",
        default=None,
        help="optional opponent-only deck pool for stationary-opponent curricula",
    )
    parser.add_argument(
        "--matchups-path",
        default=None,
        help="optional weighted exact learner/opponent matchup curriculum",
    )
    parser.add_argument(
        "--matchup-probability",
        type=float,
        default=0.0,
        help="probability of sampling an exact pair from --matchups-path",
    )
    parser.add_argument("--checkpoint-dir", default="checkpoints/entity_selfplay")
    parser.add_argument("--resume-latest", action="store_true")
    parser.add_argument("--resume-from", default=None)
    parser.add_argument(
        "--initialize-policy-from",
        default=None,
        help=(
            "initialize only model weights/config/vocabulary from a V2 policy; "
            "optimizer, update counters, simulator state, and RNG start fresh"
        ),
    )
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--updates", type=int, default=500)
    parser.add_argument("--num-envs", type=int, default=6)
    parser.add_argument("--torch-threads", type=int, default=None)
    parser.add_argument("--total-decisions", type=int, default=None)
    parser.add_argument("--checkpoint-decisions", type=int, action="append", default=[])
    parser.add_argument("--level-randomization-after", type=int, default=None)
    parser.add_argument("--mixed-level-probability", type=float, default=0.5)
    parser.add_argument("--reward-potential-scale", type=float, default=None)
    parser.add_argument(
        "--actor-workers",
        type=int,
        default=1,
        help="persistent CPU rollout processes; use >1 to parallelize the simulator",
    )
    parser.add_argument(
        "--actor-threads",
        type=int,
        default=2,
        help="PyTorch CPU threads per rollout process",
    )
    parser.add_argument(
        "--rollout-inference",
        choices=["worker", "learner"],
        default="worker",
        help=(
            "worker: each actor process runs its own CPU policy copy; learner: "
            "actor processes only step simulators and opponents and the learner "
            "process runs one batched policy forward over every environment on "
            "--actor-device (transitions do not depend on the actor partition)"
        ),
    )
    parser.add_argument(
        "--trim-rollout-entity-padding",
        action="store_true",
        help=(
            "new-lineage experiment: crop trailing masked entity slots before "
            "CPU actor inference; changes floating reductions but not observations"
        ),
    )
    parser.add_argument("--rollout-steps", type=int, default=48)
    parser.add_argument(
        "--first-rollout-audit-json",
        default=None,
        help=(
            "optional fail-closed exact digest of the first collected rollout, "
            "published before GAE or optimization"
        ),
    )
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument("--mirror-match", action="store_true")
    parser.add_argument(
        "--reward-profile",
        choices=REWARD_PROFILES,
        default=OBJECTIVE_V1,
        help="objective-v1 preserves existing checkpoints; defense-v2 adds board and danger potentials",
    )
    parser.add_argument(
        "--reward-shaping-gamma",
        type=float,
        default=None,
        help=(
            "opt-in policy-invariant shaping gamma with terminal potential zero; "
            "omit to preserve legacy checkpoint rewards"
        ),
    )
    parser.add_argument(
        "--elixir-leak-penalty-scale",
        type=float,
        default=1.0,
        help="scale the legacy full-elixir no-op penalty; use 0 for the no-leak arm",
    )
    parser.add_argument("--defense-scenario-probability", type=float, default=0.0)
    parser.add_argument("--defense-scenario-minimum-elixir", type=int, default=4)
    parser.add_argument("--defense-scenario-maximum-elixir", type=int, default=7)
    parser.add_argument("--defense-scenario-horizon-ticks", type=int, default=240)
    parser.add_argument("--defense-scenario-reward-scale", type=float, default=1.0)
    parser.add_argument(
        "--opponent-mode",
        choices=["selfplay", "noop", "random", "strategy", "checkpoint", "league"],
        default="selfplay",
        help=(
            "selfplay trains both seats with the current policy; random trains "
            "one balanced learner seat per environment against a stationary "
            "uniform-legal opponent; noop supplies no further opponent actions; "
            "strategy uses a deterministic public-info "
            "bot; checkpoint uses frozen policies; league mixes repeated "
            "random/strategy/checkpoint specifications across workers"
        ),
    )
    parser.add_argument(
        "--opponent-strategy",
        choices=STRATEGY_NAMES,
        default=None,
        help="public-information strategy used by --opponent-mode strategy",
    )
    parser.add_argument(
        "--online-strategy-teacher",
        choices=STRATEGY_NAMES,
        default=None,
        help=(
            "optional public-information teacher evaluated on the learner's "
            "own resident rollout states"
        ),
    )
    parser.add_argument(
        "--online-strategy-teacher-balanced-config",
        default=None,
        help="optional JSON BalancedStrategyConfig for the balanced learner teacher",
    )
    parser.add_argument("--online-strategy-teacher-coef", type=float, default=0.0)
    parser.add_argument(
        "--online-strategy-teacher-decision-coef", type=float, default=1.0
    )
    parser.add_argument(
        "--online-strategy-teacher-card-coef", type=float, default=1.0
    )
    parser.add_argument(
        "--online-strategy-teacher-tile-coef", type=float, default=1.0
    )
    parser.add_argument(
        "--online-strategy-teacher-play-weight", type=float, default=4.0
    )
    parser.add_argument(
        "--opponent-checkpoint",
        action="append",
        default=[],
        help="repeat to distribute frozen V2 opponents across rollout workers",
    )
    parser.add_argument(
        "--league-opponent",
        action="append",
        default=[],
        metavar="RANDOM_STRATEGY_OR_CHECKPOINT",
        help=(
            "repeat in league mode; each value is 'random', 'strategy:NAME', "
            "or a frozen V2 checkpoint path, distributed across workers"
        ),
    )
    parser.add_argument(
        "--pfsp-report",
        default=None,
        help=(
            "strategy-benchmark JSON whose PFSP weights fill strategy worker "
            "slots in league mode"
        ),
    )
    parser.add_argument(
        "--pfsp-strategy-workers",
        type=int,
        default=None,
        help=(
            "number of league slots allocated from --pfsp-report; one slot is "
            "one paired logical matchup on simple-pytorch"
        ),
    )
    parser.add_argument(
        "--engine-fast-path", choices=["off", "shadow", "on"], default="off"
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "mps", "cuda"],
        default="auto",
        help="PPO learner device; auto uses MPS/CUDA for sequence batches",
    )
    parser.add_argument(
        "--actor-device",
        choices=["auto", "cpu", "mps", "cuda"],
        default="auto",
        help="rollout inference device; auto prefers CPU for low-latency batches",
    )
    parser.add_argument(
        "--hazard-conditioned-rollouts",
        action="store_true",
        help=(
            "sample PPO rollouts from the same cumulative play-hazard hierarchy "
            "used by deterministic evaluation"
        ),
    )
    parser.add_argument("--d-model", type=int, default=128)
    parser.add_argument("--num-heads", type=int, default=4)
    parser.add_argument("--actor-layers", type=int, default=4)
    parser.add_argument("--critic-layers", type=int, default=2)
    parser.add_argument("--memory-size", type=int, default=256)
    parser.add_argument(
        "--action-value-head",
        action="store_true",
        help=(
            "fresh-lineage actor-visible factorized action-value head; starts "
            "behavior-closed and must be paired with --action-value-coef"
        ),
    )
    parser.add_argument(
        "--fresh-factorized-action-head",
        action="store_true",
        help=(
            "fresh-lineage explicit play/wait/ability gate, shared slot-equivariant "
            "mechanics-aware card pointer, and unchanged exact placement heatmap"
        ),
    )
    parser.add_argument(
        "--encoder-kind",
        choices=("attention", "deepsets"),
        default="attention",
        help="entity interaction encoder for a fresh policy",
    )
    parser.add_argument(
        "--memory-kind",
        choices=("lstm", "gru", "structured", "feedforward"),
        default="lstm",
        help="temporal core for a fresh policy",
    )
    parser.add_argument(
        "--decoder-kind",
        choices=("attention", "global"),
        default="attention",
        help="tile decoder for a fresh policy",
    )
    parser.add_argument(
        "--card-input-mode",
        choices=("hybrid", "residual-hybrid", "id-only", "mechanics-only"),
        default="hybrid",
        help="learned card identity, exact mechanics, or both",
    )
    parser.add_argument(
        "--add-placement-prior",
        action="store_true",
        help=(
            "add a zero-initialized card-conditioned placement prior while "
            "resuming a checkpoint"
        ),
    )
    parser.add_argument(
        "--add-public-history-slots",
        type=int,
        default=0,
        help=(
            "add a zero-output residual over this many recent public opponent "
            "card plays while resuming a checkpoint"
        ),
    )
    parser.add_argument(
        "--add-public-seen-card-slots",
        type=int,
        default=0,
        help=(
            "add persistent public opponent-card discovery slots while resuming; "
            "requires public history in the resulting model"
        ),
    )
    parser.add_argument(
        "--add-action-type-adapter",
        action="store_true",
        help=(
            "add a zero-initialized contextual residual over only the six "
            "deploy/wait/ability logits while resuming a checkpoint"
        ),
    )
    parser.add_argument(
        "--add-structured-resource-policy-gate",
        action="store_true",
        help=(
            "add a zero-initialized gate between a structured opponent-resource "
            "belief and the policy while resuming a checkpoint"
        ),
    )
    parser.add_argument(
        "--add-play-hazard-adapter-size",
        type=int,
        default=0,
        help=(
            "add a zero-initialized scalar contextual residual to the play "
            "hazard while resuming a checkpoint"
        ),
    )
    parser.add_argument(
        "--play-hazard-adapter-enemy-y-gate",
        type=float,
        default=1.0,
        help=(
            "canonical public enemy-troop y threshold below which a newly "
            "added hazard adapter may change timing"
        ),
    )
    parser.add_argument(
        "--enable-structured-deterministic-resource",
        action="store_true",
        help=(
            "replace learned opponent-resource updates with exact clock regen "
            "minus public observed card costs while resuming a structured checkpoint"
        ),
    )
    parser.add_argument(
        "--add-repair-adapter-size",
        type=int,
        default=0,
        help=(
            "add a zero-initialized dense repair adapter while resuming a "
            "checkpoint; the saved base and prototype policy remain unchanged"
        ),
    )
    parser.add_argument(
        "--add-repair-stage-size",
        type=int,
        default=0,
        help=(
            "append a zero-initialized dense repair stage while resuming a "
            "checkpoint; earlier repair stages and guards remain unchanged"
        ),
    )
    parser.add_argument(
        "--trainable-prefix",
        action="append",
        default=[],
        help=(
            "restrict optimization to parameter names beginning with this prefix; "
            "repeat for multiple prefixes and use with --reset-optimizer"
        ),
    )
    parser.add_argument("--learning-rate", type=float, default=2.5e-4)
    parser.add_argument(
        "--reset-optimizer",
        action="store_true",
        help="resume model weights and counters without restoring optimizer moments",
    )
    parser.add_argument("--gamma", type=float, default=0.995)
    parser.add_argument("--gae-lambda", type=float, default=0.95)
    parser.add_argument("--clip-ratio", type=float, default=0.2)
    parser.add_argument("--value-coef", type=float, default=0.5)
    parser.add_argument(
        "--action-value-coef",
        type=float,
        default=0.0,
        help="Huber coefficient for selected actor-visible action returns",
    )
    parser.add_argument("--entropy-coef", type=float, default=0.01)
    parser.add_argument(
        "--action-type-entropy-coef",
        type=float,
        default=None,
        help="override entropy regularization for card/wait/ability selection",
    )
    parser.add_argument(
        "--location-entropy-coef",
        type=float,
        default=None,
        help="override entropy regularization for placement conditional on card choice",
    )
    parser.add_argument(
        "--conditional-slot-entropy-coef",
        type=float,
        default=0.0,
        help=(
            "additional entropy regularization among legal hand slots, "
            "conditional on playing; does not reward play over wait"
        ),
    )
    parser.add_argument(
        "--anchor-checkpoint",
        default=None,
        help="frozen V2 checkpoint used for parameter-space anti-forgetting",
    )
    parser.add_argument(
        "--anchor-l2-coef",
        type=float,
        default=0.0,
        help="coefficient on half squared distance from --anchor-checkpoint",
    )
    parser.add_argument(
        "--anchor-policy-kl-coef",
        type=float,
        default=0.0,
        help=(
            "coefficient on forward action-distribution KL from the frozen "
            "--anchor-checkpoint on learner rollout states"
        ),
    )
    parser.add_argument(
        "--rehearsal-corpus",
        default=None,
        help=("expert corpus supplying recurrent action rehearsal during PPO updates"),
    )
    parser.add_argument(
        "--rehearsal-sequence-length",
        type=int,
        default=None,
        help=(
            "expert recurrent chunk length; defaults to --rollout-steps for "
            "backward compatibility"
        ),
    )
    parser.add_argument(
        "--rehearsal-coef",
        type=float,
        default=0.0,
        help="coefficient on the auxiliary recurrent rehearsal loss",
    )
    parser.add_argument(
        "--rehearsal-loss-component",
        choices=("joint", "location", "type"),
        default="joint",
        help=(
            "train expert joint actions, only placement location conditional "
            "on the expert slot, or only deploy/wait/card-slot action type"
        ),
    )
    parser.add_argument(
        "--rehearsal-batch-sequences",
        type=int,
        default=1,
        help="expert sequence chunks sampled per PPO optimizer step",
    )
    parser.add_argument(
        "--causal-rehearsal-corpus",
        default=None,
        help="causal recurrent corpus supplying trusted play/wait supervision",
    )
    parser.add_argument(
        "--causal-rehearsal-public-sidecar",
        default=None,
        help="aligned public-v2 observations and label-independent masks",
    )
    parser.add_argument(
        "--causal-rehearsal-sequence-length",
        type=int,
        default=None,
        help="causal rehearsal recurrent chunk length; defaults to rollout steps",
    )
    parser.add_argument(
        "--causal-rehearsal-coef",
        type=float,
        default=0.0,
        help="coefficient on trusted public-frame play/wait/ability loss",
    )
    parser.add_argument(
        "--causal-rehearsal-decision-coef",
        type=float,
        default=1.0,
        help="play/wait/ability loss relative to the causal rehearsal coefficient",
    )
    parser.add_argument(
        "--causal-rehearsal-decision-positive-weight",
        type=float,
        default=None,
        help=(
            "optional corpus-specific positive weight for the play hazard BCE; "
            "defaults to the checkpoint's human rare-event calibration"
        ),
    )
    parser.add_argument(
        "--causal-rehearsal-card-coef",
        type=float,
        default=0.0,
        help=(
            "card-choice loss relative to the causal rehearsal timing loss; "
            "uses only trusted public-mask-compatible placement labels"
        ),
    )
    parser.add_argument(
        "--causal-rehearsal-tile-coef",
        type=float,
        default=0.0,
        help=(
            "placement-tile loss relative to causal rehearsal timing; rows "
            "must carry explicit trusted tile supervision"
        ),
    )
    parser.add_argument(
        "--causal-rehearsal-batch-sequences",
        type=int,
        default=1,
        help="causal public-frame chunks sampled per PPO optimizer step",
    )
    parser.add_argument(
        "--causal-spatial-rehearsal-corpus",
        default=None,
        help=(
            "second causal corpus supplying trusted card/tile supervision while "
            "leaving the primary timing objective unchanged"
        ),
    )
    parser.add_argument(
        "--causal-spatial-rehearsal-public-sidecar",
        default=None,
        help="aligned public-v2 observations for the second spatial corpus",
    )
    parser.add_argument(
        "--causal-spatial-rehearsal-sequence-length",
        type=int,
        default=None,
        help="second causal rehearsal chunk length; defaults to rollout steps",
    )
    parser.add_argument(
        "--causal-spatial-rehearsal-coef",
        type=float,
        default=0.0,
        help="coefficient on the independent causal card/tile objective",
    )
    parser.add_argument(
        "--causal-spatial-rehearsal-card-coef",
        type=float,
        default=1.0,
        help="trusted card-choice coefficient within the spatial objective",
    )
    parser.add_argument(
        "--causal-spatial-rehearsal-tile-coef",
        type=float,
        default=0.0,
        help="trusted placement-tile coefficient within the spatial objective",
    )
    parser.add_argument(
        "--causal-spatial-rehearsal-batch-sequences",
        type=int,
        default=1,
        help="second causal corpus chunks sampled per PPO optimizer step",
    )
    parser.add_argument(
        "--anchor-rehearsal-corpus",
        default=None,
        help=(
            "recurrent corpus states on which to preserve the frozen "
            "--anchor-checkpoint action distribution"
        ),
    )
    parser.add_argument(
        "--anchor-rehearsal-sequence-length",
        type=int,
        default=None,
        help=("anchor-rehearsal recurrent chunk length; defaults to --rollout-steps"),
    )
    parser.add_argument(
        "--anchor-rehearsal-coef",
        type=float,
        default=0.0,
        help="coefficient on frozen-policy KL over anchor rehearsal states",
    )
    parser.add_argument(
        "--anchor-rehearsal-batch-sequences",
        type=int,
        default=1,
        help="anchor-rehearsal chunks sampled per PPO optimizer step",
    )
    parser.add_argument(
        "--anchor-rehearsal-loss-component",
        choices=("joint", "location", "type"),
        default="joint",
        help=(
            "preserve the frozen anchor's joint distribution, conditional "
            "placement geometry, or slot/no-op/ability distribution on "
            "anchor-rehearsal states"
        ),
    )
    parser.add_argument("--hand-aux-coef", type=float, default=0.02)
    parser.add_argument("--elixir-aux-coef", type=float, default=0.05)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--sequence-batch-size", type=int, default=2)
    parser.add_argument("--target-kl", type=float, default=0.03)
    parser.add_argument(
        "--critic-warmup-updates",
        type=int,
        default=0,
        help=(
            "first N updates optimize only the separate critic (value loss) with "
            "every actor parameter frozen; used after a scripted warm start"
        ),
    )
    parser.add_argument(
        "--council-arm",
        choices=("scripted", "scratch"),
        default=None,
        help="council pilot initialization arm, recorded in checkpoint metadata",
    )
    parser.add_argument(
        "--preflight-no-update",
        action="store_true",
        help=(
            "launch preflight only: run startup, initialization, environment "
            "creation, one rollout collection and the (critic warm-up and) PPO "
            "loss/backward code paths, then exit before any optimizer.step(). "
            "Writes no checkpoint, asserts bit-identical weights, and skips the "
            "Tier A admission lookup (a preflight is never gameplay fitting)"
        ),
    )
    parser.add_argument(
        "--preflight-rollout-steps",
        type=int,
        default=None,
        help="cap the single preflight rollout at this many steps per environment",
    )
    parser.add_argument(
        "--preflight-report-json",
        type=Path,
        default=None,
        help="write the preflight weight-digest/timing receipt here (new file)",
    )
    parser.add_argument("--save-every", type=int, default=10)
    parser.add_argument("--log-every", type=int, default=1)
    parser.add_argument("--no-lr-anneal", dest="lr_anneal", action="store_false")
    parser.add_argument(
        "--quiet-engine", dest="quiet_engine", action="store_true", default=True
    )
    parser.add_argument("--no-quiet-engine", dest="quiet_engine", action="store_false")
    parser.add_argument("--recurrent-update-mode", choices=("full-prefix", "stored-state"), default=argparse.SUPPRESS)
    parser.add_argument("--tbptt-chunk", type=int, default=argparse.SUPPRESS)
    parser.add_argument("--tbptt-burn-in", type=int, default=argparse.SUPPRESS)
    parser.add_argument("--recurrent-config", type=Path, default=argparse.SUPPRESS)
    from .tbptt import apply_cli_config
    return apply_cli_config(parser.parse_args())


def _load_resume_state(
    args: argparse.Namespace,
    directory: Path,
    device: torch.device,
) -> tuple[dict[str, Any] | None, Path | None]:
    if args.resume_latest and args.resume_from:
        raise ValueError("Use only one of --resume-latest or --resume-from")
    path: Path | None = None
    if args.resume_from:
        path = resolve_path(args.resume_from, must_exist=True)
    elif args.resume_latest:
        path = find_latest_checkpoint(directory)
    if path is None:
        return None, None
    return torch.load(path, map_location=device, weights_only=False), path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_initial_policy_state(
    args: argparse.Namespace,
    device: torch.device,
) -> tuple[dict[str, Any] | None, Path | None]:
    if not args.initialize_policy_from:
        return None, None
    # Weights-only initialization is verified for two paths: the Simple Gym
    # (exact vocabulary/capacity contract below) and the python-backend council
    # pilot at public contract v4, where council_pilot.validate_council_initial_policy
    # binds contract/semantics versions, vocabulary, provenance digests,
    # BudgetSnapshot, published opponent hash and a post-load weight digest.
    # Every other python-backend run stays gated.
    council_path = (
        args.simulation_backend == "python"
        and getattr(args, "council_config", None) is not None
        and args.public_contract_version == 4
    )
    if args.simulation_backend != "simple-pytorch" and not council_path:
        raise ValueError(
            "--initialize-policy-from is gated for simple-pytorch and the "
            "public-v4 council pilot path only"
        )
    if args.resume_latest or args.resume_from:
        raise ValueError(
            "--initialize-policy-from cannot be combined with checkpoint resume"
        )
    path = resolve_path(args.initialize_policy_from, must_exist=True)
    payload = torch.load(path, map_location=device, weights_only=False)
    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("initial policy is not a V2 checkpoint")
    if payload.get("model_type") != "entity_spatial_recurrent":
        raise ValueError("initial policy has an unsupported model type")
    if not isinstance(payload.get("model_config"), dict):
        raise TypeError("initial policy has no model configuration")
    if not isinstance(payload.get("model_state_dict"), dict):
        raise TypeError("initial policy has no model state")
    token_names = payload.get("token_names")
    if not isinstance(token_names, (list, tuple)) or not token_names:
        raise ValueError("initial policy has no token vocabulary")
    return payload, path


def _validate_simple_initial_policy_contract(
    payload: dict[str, Any],
    *,
    token_names: tuple[str, ...],
    max_entities: int,
) -> PolicyConfig:
    """Accept only policy state the fresh Simple Gym can consume exactly."""

    configured_tokens = tuple(str(name) for name in payload["token_names"])
    if configured_tokens != token_names:
        raise ValueError("initial policy token vocabulary does not match Simple Gym")
    config = PolicyConfig.from_dict(payload["model_config"])
    if config.num_tokens != len(token_names):
        raise ValueError("initial policy token count does not match its vocabulary")
    if not config.canonical_lane_globals:
        raise ValueError("initial policy must use canonical lane globals")
    if config.public_history_slots or config.public_seen_card_slots:
        raise ValueError("Simple Gym initialization does not support history slots")
    if config.structured_deterministic_resource_enabled:
        raise ValueError(
            "Simple Gym initialization does not support deterministic resource state"
        )
    # Entity count is a padding/validation bound, not a learned tensor axis in
    # the set-attention policy. Rebinding it preserves every parameter; the
    # runtime admission gate independently proves whether the requested bound
    # is large enough for the configured deck pool.
    return (
        config
        if config.max_entities == max_entities
        else replace(config, max_entities=max_entities)
    )


def restore_optimizer_state(
    optimizer: torch.optim.Optimizer,
    state_dict: dict[str, Any],
    *,
    learning_rate: float,
) -> None:
    """Restore optimizer moments while keeping the current run's requested LR."""

    optimizer.load_state_dict(state_dict)
    for group in optimizer.param_groups:
        group["lr"] = learning_rate


def _canonical_lane_globals_for_run(
    *,
    actor_observation_domain: str,
    resume_config: PolicyConfig | None,
    simulation_backend: str = "python",
) -> bool:
    """Keep the observation builder and checkpoint contract on one lane frame."""

    if resume_config is not None:
        return bool(resume_config.canonical_lane_globals)
    if simulation_backend == "simple-pytorch":
        return True
    return actor_observation_domain in {"causal-vision-v1", "causal-frame-v1"}


def _validate_simple_pytorch_args(args: argparse.Namespace) -> None:
    """Fail before side effects unless the fresh dense-Gym contract is exact."""

    if (args.online_strategy_teacher is None) != (
        args.online_strategy_teacher_coef == 0.0
    ):
        raise ValueError(
            "online strategy teacher and a positive teacher coefficient are "
            "required together"
        )
    if args.online_strategy_teacher_coef < 0.0:
        raise ValueError("online strategy teacher coefficient cannot be negative")
    for name in (
        "online_strategy_teacher_decision_coef",
        "online_strategy_teacher_card_coef",
        "online_strategy_teacher_tile_coef",
    ):
        if getattr(args, name) < 0.0:
            raise ValueError(f"{name} cannot be negative")
    if args.online_strategy_teacher_play_weight < 1.0:
        raise ValueError("online strategy teacher play weight must be at least one")
    if (
        args.online_strategy_teacher_balanced_config is not None
        and args.online_strategy_teacher != "balanced"
    ):
        raise ValueError(
            "online balanced teacher config requires the balanced teacher"
        )
    if args.online_strategy_teacher is not None and args.opponent_mode == "selfplay":
        raise ValueError("online strategy teacher requires a learner-only opponent")

    if args.simulation_backend != "simple-pytorch":
        if args.simple_learner_sampling_temperature != 1.0:
            raise ValueError(
                "--simple-learner-sampling-temperature requires simple-pytorch"
            )
        return
    if (
        not math.isfinite(args.simple_learner_sampling_temperature)
        or args.simple_learner_sampling_temperature <= 0.0
    ):
        raise ValueError(
            "--simple-learner-sampling-temperature must be finite and positive"
        )
    if args.actor_workers != 1:
        raise ValueError("simple-pytorch requires --actor-workers 1")
    if args.simple_max_entities < 16:
        raise ValueError("simple-pytorch requires --simple-max-entities >= 16")
    if args.simple_max_effects < 1:
        raise ValueError("simple-pytorch requires --simple-max-effects >= 1")
    if args.resume_latest or args.resume_from:
        raise ValueError("simple-pytorch is fresh-only until exact resume is gated")
    if args.opponent_mode not in {
        "selfplay",
        "noop",
        "random",
        "strategy",
        "league",
        "checkpoint",
    }:
        raise ValueError(
            "simple-pytorch supports selfplay, noop, random, strategy, league, "
            "or checkpoint"
        )
    if args.opponent_mode != "selfplay" and args.mirror_match:
        raise ValueError(
            "simple-pytorch stationary opponents require asymmetric deck rows"
        )
    if args.opponent_mode == "checkpoint" and len(args.opponent_checkpoint) != 1:
        raise ValueError(
            "simple-pytorch checkpoint mode requires exactly one frozen checkpoint"
        )
    if args.opponent_mode == "league":
        simple_league = tuple(args.league_opponent)
        unknown_strategies = [
            value.removeprefix("strategy:")
            for value in simple_league
            if value.startswith("strategy:")
            and value.removeprefix("strategy:") not in STRATEGY_NAMES
        ]
        if unknown_strategies:
            raise ValueError(
                "simple-pytorch league contains unknown strategies: "
                + ", ".join(sorted(set(unknown_strategies)))
            )
        checkpoint_specs = {
            value
            for value in simple_league
            if value != "random" and not value.startswith("strategy:")
        }
        if len(checkpoint_specs) > 1:
            raise ValueError(
                "simple-pytorch league supports one unique checkpoint policy"
            )
        if not args.pfsp_report and len(set(simple_league)) < 2:
            raise ValueError(
                "simple-pytorch league currently requires at least two explicit "
                "opponents or a PFSP report"
            )
    if args.simple_checkpoint_opponent_deck_name is not None:
        has_checkpoint = args.opponent_mode == "checkpoint" or (
            args.opponent_mode == "league"
            and any(
                value != "random" and not value.startswith("strategy:")
                for value in args.league_opponent
            )
        )
        if not has_checkpoint:
            raise ValueError(
                "--simple-checkpoint-opponent-deck-name requires a checkpoint "
                "opponent"
            )
    if args.actor_observation_domain != "simulator-exact":
        raise ValueError(
            "simple-pytorch owns an exact public projection actor domain"
        )
    if args.reward_profile != OBJECTIVE_V1 or args.reward_shaping_gamma is not None:
        raise ValueError(
            "simple-pytorch uses only its persisted objective-v1-gamma-v1 reward"
        )
    if args.elixir_leak_penalty_scale != 0.0:
        raise ValueError(
            "simple-pytorch requires --elixir-leak-penalty-scale 0"
        )
    if args.engine_fast_path != "off":
        raise ValueError("simple-pytorch does not compose the legacy engine fast path")
    if args.max_ticks != STANDARD_MATCH_TICKS:
        raise ValueError("simple-pytorch currently requires the standard match horizon")
    if (
        args.sampling_decks_path is not None
        or args.learner_sampling_decks_path is not None
        or args.opponent_sampling_decks_path is not None
        or args.matchups_path is not None
        or args.defense_scenario_probability != 0.0
    ):
        raise ValueError(
            "simple-pytorch deck sampling is owned by its supported-deck artifact"
        )


_MAIN_STARTED = time.perf_counter()


def _finish_launch_preflight(
    preflight: dict[str, Any],
    *,
    args: argparse.Namespace,
    model: ClasherPolicy,
    actor_model: ClasherPolicy,
    optimizer: torch.optim.Optimizer,
    rollout: RolloutBatch,
    advantages: np.ndarray,
    returns: np.ndarray,
    run_ppo_update: Any,
    scheduled_critic_only: bool,
    collect_seconds: float,
    training_monitor: Any,
    update: int,
    directory: Path,
) -> dict[str, Any]:
    """Exercise the scheduled update path with zero optimizer steps, then prove it.

    The scheduled path runs first (critic warm-up for the scripted arm, full PPO
    for scratch); when that was critic-only, the full PPO path also runs on the
    same rollout so both code paths are covered. Losses, backward, gradient
    finiteness checks and clipping all run; ``optimizer.step()`` never does.
    """
    from .council_pilot import state_dict_sha256

    paths = [("critic_warmup" if scheduled_critic_only else "ppo", scheduled_critic_only)]
    if scheduled_critic_only:
        paths.append(("ppo", False))
    update_stats: dict[str, dict[str, float]] = {}
    started = time.perf_counter()
    for label, critic_only in paths:
        stats = run_ppo_update(
            rollout,
            advantages,
            returns,
            critic_only=critic_only,
            apply_optimizer_step=False,
        )
        if stats["optimizer_steps"] != 0.0:
            raise RuntimeError("preflight update reported optimizer steps")
        if stats["evaluated_minibatches"] <= 0:
            raise RuntimeError("preflight did not evaluate any PPO minibatch")
        update_stats[label] = {key: float(value) for key, value in stats.items()}
    update_seconds = time.perf_counter() - started
    if training_monitor is not None:
        training_monitor.observe_update(
            update=update,
            learner_decisions=int(rollout.transitions),
            actions=rollout.actions,
            hand_ids=rollout.hand_ids,
            episodes_finished=rollout.episodes_finished,
            stats=update_stats[paths[-1][0]],
            action_masks=rollout.action_masks,
        )
    after = state_dict_sha256(model.state_dict())
    actor_after = state_dict_sha256(actor_model.state_dict())
    gradients_left = [
        name for name, parameter in model.named_parameters() if parameter.grad is not None
    ]
    written = sorted(str(path) for path in directory.rglob("*.pt"))
    preflight.update(
        {
            "weights_sha256_after": after,
            "actor_weights_sha256_after": actor_after,
            "weights_unchanged": after == preflight["weights_sha256_before"],
            "optimizer_state_entries_after": len(optimizer.state),
            "gradients_left_after": len(gradients_left),
            "checkpoints_written": written,
            "rollout_steps": int(rollout.actions.shape[1]),
            "rollout_transitions": int(rollout.transitions),
            "rollout_episodes_finished": int(rollout.episodes_finished),
            "rollout_rejected_actions": (
                int(np.count_nonzero(~rollout.action_success))
                if rollout.action_success is not None
                else 0
            ),
            "update_paths": [label for label, _ in paths],
            "update_stats": update_stats,
            "collect_seconds": collect_seconds,
            "update_seconds": update_seconds,
            "total_seconds": time.perf_counter() - _MAIN_STARTED,
        }
    )
    ok = (
        preflight["weights_unchanged"]
        and actor_after == after
        and not optimizer.state
        and not gradients_left
        and not written
    )
    preflight["status"] = "passed" if ok else "failed"
    if args.preflight_report_json is not None:
        report = Path(args.preflight_report_json)
        report.parent.mkdir(parents=True, exist_ok=True)
        with report.open("x") as stream:
            json.dump(preflight, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(
        f"preflight_status={preflight['status']} "
        f"weights_before={preflight['weights_sha256_before']} weights_after={after} "
        f"update_paths={','.join(preflight['update_paths'])} "
        f"collect_s={collect_seconds:.2f} update_s={update_seconds:.2f}",
        flush=True,
    )
    if not ok:
        raise RuntimeError("launch preflight changed state or wrote a checkpoint")
    return preflight


# Resume RNG continuity (pilot/diagnosis-1M bug 3). A resumed run used to
# re-seed every stream from ``--seed`` and replay the first segment's games and
# opponent assignments. Now each saved checkpoint gets a learner RNG sidecar
# (Python, NumPy, Torch) that a resume restores, and every resumed segment
# derives a fresh base seed for environments, opponents and actor processes,
# whose RNG lives in other processes and cannot be carried over.
RNG_STATE_DIRECTORY = "rng-state"
RUN_SEGMENTS_FILE = "run-segments.jsonl"
_RESUME_SEED_LIMIT = 2**31 - 2**27  # leaves room for per-env/worker seed offsets


def rng_state_path(directory: Path, update: int) -> Path:
    return Path(directory) / RNG_STATE_DIRECTORY / f"update_{update:06d}.pt"


def capture_rng_state() -> dict[str, Any]:
    import random

    state: dict[str, Any] = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch": torch.get_rng_state(),
    }
    if torch.backends.mps.is_available():
        state["torch_mps"] = torch.mps.get_rng_state()
    if torch.cuda.is_available():
        state["torch_cuda"] = torch.cuda.get_rng_state_all()
    return state


def restore_rng_state(state: dict[str, Any]) -> None:
    import random

    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch"])
    if "torch_mps" in state and torch.backends.mps.is_available():
        torch.mps.set_rng_state(state["torch_mps"])
    if "torch_cuda" in state and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(state["torch_cuda"])


def save_rng_state(
    directory: Path, *, checkpoint: Path, update: int, rollout_seed: int
) -> Path:
    path = rng_state_path(directory, update)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    torch.save(
        {
            "schema": "clasher.train-rng-state.v1",
            "update": update,
            "checkpoint": checkpoint.name,
            "checkpoint_sha256": _sha256(checkpoint),
            "rollout_seed": rollout_seed,
            "state": capture_rng_state(),
        },
        temporary,
    )
    os.replace(temporary, path)
    return path


def load_rng_state(directory: Path, *, checkpoint: Path, update: int) -> dict | None:
    """The sidecar saved with this exact checkpoint, or None if absent/mismatched."""
    path = rng_state_path(directory, update)
    if not path.exists():
        return None
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if payload.get("update") != update or payload.get(
        "checkpoint_sha256"
    ) != _sha256(checkpoint):
        return None
    return payload


def resume_rollout_seed(seed: int, *, start_update: int, segment: int) -> int:
    """Base seed for environments, opponents and actor processes of a resumed
    segment, distinct per (seed, start update, segment index)."""
    state = np.random.SeedSequence(
        [int(seed), int(start_update), int(segment), 0x5EED]
    ).generate_state(1, dtype=np.uint64)[0]
    return int(state % _RESUME_SEED_LIMIT)


def entropy_recipe_record(args: argparse.Namespace) -> dict[str, Any]:
    """Entropy coefficients exactly as ppo_update combines them."""
    joint = args.action_type_entropy_coef is None and args.location_entropy_coef is None
    return {
        "entropy_coef": args.entropy_coef,
        "action_type_entropy_coef": args.action_type_entropy_coef,
        "location_entropy_coef": args.location_entropy_coef,
        "conditional_slot_entropy_coef": args.conditional_slot_entropy_coef,
        "joint_entropy_term_applies": joint,
        "effective_type_coef": (
            None
            if joint
            else (
                args.entropy_coef
                if args.action_type_entropy_coef is None
                else args.action_type_entropy_coef
            )
        ),
        "effective_location_coef": (
            None
            if joint
            else (
                args.entropy_coef
                if args.location_entropy_coef is None
                else args.location_entropy_coef
            )
        ),
    }


def card_costs_for_monitor(builder: StructuredObservationBuilder) -> dict[str, int]:
    costs: dict[str, int] = {}
    for name in builder.token_names:
        if str(name).startswith("<"):
            continue
        try:
            stats = builder.loader.get_card(str(name))
        except Exception:  # noqa: BLE001 - monitoring metadata only
            stats = None
        cost = getattr(stats, "mana_cost", None) if stats is not None else None
        if isinstance(cost, (int, float)) and cost > 0:
            costs[str(name)] = int(round(float(cost)))
    return costs


def main() -> None:
    global _USE_TRIMMED_ROLLOUT_ENTITY_PADDING
    global _MAIN_STARTED
    _MAIN_STARTED = time.perf_counter()
    args = parse_args()
    _validate_simple_pytorch_args(args)
    _USE_TRIMMED_ROLLOUT_ENTITY_PADDING = bool(args.trim_rollout_entity_padding)
    if args.num_envs <= 0 or args.rollout_steps <= 0:
        raise ValueError("num_envs and rollout_steps must be positive")
    if args.critic_warmup_updates < 0:
        raise ValueError("--critic-warmup-updates must be nonnegative")
    if args.critic_warmup_updates and not (
        args.initialize_policy_from or args.resume_from or args.resume_latest
    ):
        raise ValueError(
            "critic warm-up protects an initialized actor; a fresh policy has none"
        )
    first_rollout_audit_path = (
        Path(args.first_rollout_audit_json).expanduser().resolve()
        if args.first_rollout_audit_json is not None
        else None
    )
    if first_rollout_audit_path is not None and first_rollout_audit_path.exists():
        raise FileExistsError(
            f"refusing to overwrite rollout audit: {first_rollout_audit_path}"
        )
    if args.actor_workers <= 0 or args.actor_workers > args.num_envs:
        raise ValueError("actor_workers must be between 1 and num_envs")
    if args.actor_threads <= 0:
        raise ValueError("actor_threads must be positive")
    if args.reward_shaping_gamma is not None and not (
        0.0 < args.reward_shaping_gamma <= 1.0
    ):
        raise ValueError("--reward-shaping-gamma must be in (0, 1]")
    if args.elixir_leak_penalty_scale < 0.0:
        raise ValueError("--elixir-leak-penalty-scale must be non-negative")
    if args.anchor_l2_coef < 0.0:
        raise ValueError("--anchor-l2-coef must be non-negative")
    if args.anchor_policy_kl_coef < 0.0:
        raise ValueError("--anchor-policy-kl-coef must be non-negative")
    if args.rehearsal_coef < 0.0:
        raise ValueError("--rehearsal-coef must be non-negative")
    if args.rehearsal_batch_sequences <= 0:
        raise ValueError("--rehearsal-batch-sequences must be positive")
    if (
        args.rehearsal_sequence_length is not None
        and args.rehearsal_sequence_length <= 0
    ):
        raise ValueError("--rehearsal-sequence-length must be positive")
    if bool(args.rehearsal_corpus) != (args.rehearsal_coef > 0.0):
        raise ValueError(
            "--rehearsal-corpus and a positive --rehearsal-coef require each other"
        )
    if args.causal_rehearsal_coef < 0.0:
        raise ValueError("--causal-rehearsal-coef must be non-negative")
    if args.causal_rehearsal_decision_coef < 0.0:
        raise ValueError("--causal-rehearsal-decision-coef must be non-negative")
    if (
        args.causal_rehearsal_decision_positive_weight is not None
        and args.causal_rehearsal_decision_positive_weight <= 0.0
    ):
        raise ValueError(
            "--causal-rehearsal-decision-positive-weight must be positive"
        )
    if args.causal_rehearsal_card_coef < 0.0:
        raise ValueError("--causal-rehearsal-card-coef must be non-negative")
    if args.causal_rehearsal_tile_coef < 0.0:
        raise ValueError("--causal-rehearsal-tile-coef must be non-negative")
    if args.causal_rehearsal_batch_sequences <= 0:
        raise ValueError("--causal-rehearsal-batch-sequences must be positive")
    if (
        args.causal_rehearsal_sequence_length is not None
        and args.causal_rehearsal_sequence_length <= 0
    ):
        raise ValueError("--causal-rehearsal-sequence-length must be positive")
    causal_rehearsal_paths = bool(args.causal_rehearsal_corpus) and bool(
        args.causal_rehearsal_public_sidecar
    )
    if bool(args.causal_rehearsal_corpus) != bool(
        args.causal_rehearsal_public_sidecar
    ) or causal_rehearsal_paths != (args.causal_rehearsal_coef > 0.0):
        raise ValueError(
            "--causal-rehearsal-corpus, --causal-rehearsal-public-sidecar, "
            "and a positive --causal-rehearsal-coef require each other"
        )
    if args.causal_spatial_rehearsal_coef < 0.0:
        raise ValueError("--causal-spatial-rehearsal-coef must be non-negative")
    if args.causal_spatial_rehearsal_card_coef < 0.0:
        raise ValueError(
            "--causal-spatial-rehearsal-card-coef must be non-negative"
        )
    if args.causal_spatial_rehearsal_tile_coef < 0.0:
        raise ValueError(
            "--causal-spatial-rehearsal-tile-coef must be non-negative"
        )
    if args.causal_spatial_rehearsal_batch_sequences <= 0:
        raise ValueError(
            "--causal-spatial-rehearsal-batch-sequences must be positive"
        )
    if (
        args.causal_spatial_rehearsal_sequence_length is not None
        and args.causal_spatial_rehearsal_sequence_length <= 0
    ):
        raise ValueError(
            "--causal-spatial-rehearsal-sequence-length must be positive"
        )
    causal_spatial_paths = bool(args.causal_spatial_rehearsal_corpus) and bool(
        args.causal_spatial_rehearsal_public_sidecar
    )
    if bool(args.causal_spatial_rehearsal_corpus) != bool(
        args.causal_spatial_rehearsal_public_sidecar
    ) or causal_spatial_paths != (args.causal_spatial_rehearsal_coef > 0.0):
        raise ValueError(
            "--causal-spatial-rehearsal-corpus, "
            "--causal-spatial-rehearsal-public-sidecar, and a positive "
            "--causal-spatial-rehearsal-coef require each other"
        )
    if args.causal_spatial_rehearsal_coef > 0.0 and not (
        args.causal_spatial_rehearsal_card_coef > 0.0
        or args.causal_spatial_rehearsal_tile_coef > 0.0
    ):
        raise ValueError(
            "causal spatial rehearsal requires a positive card or tile coefficient"
        )
    if args.anchor_rehearsal_coef < 0.0:
        raise ValueError("--anchor-rehearsal-coef must be non-negative")
    if args.anchor_rehearsal_batch_sequences <= 0:
        raise ValueError("--anchor-rehearsal-batch-sequences must be positive")
    if (
        args.anchor_rehearsal_sequence_length is not None
        and args.anchor_rehearsal_sequence_length <= 0
    ):
        raise ValueError("--anchor-rehearsal-sequence-length must be positive")
    if bool(args.anchor_rehearsal_corpus) != (args.anchor_rehearsal_coef > 0.0):
        raise ValueError(
            "--anchor-rehearsal-corpus and a positive "
            "--anchor-rehearsal-coef require each other"
        )
    if args.add_repair_adapter_size < 0:
        raise ValueError("--add-repair-adapter-size must be non-negative")
    if args.add_play_hazard_adapter_size < 0:
        raise ValueError("--add-play-hazard-adapter-size must be non-negative")
    if not 0.0 < args.play_hazard_adapter_enemy_y_gate <= 1.0:
        raise ValueError("--play-hazard-adapter-enemy-y-gate must be in (0, 1]")
    if (
        args.play_hazard_adapter_enemy_y_gate < 1.0
        and not args.add_play_hazard_adapter_size
    ):
        raise ValueError(
            "--play-hazard-adapter-enemy-y-gate requires a new hazard adapter"
        )
    if args.add_public_history_slots < 0:
        raise ValueError("--add-public-history-slots must be non-negative")
    if args.add_repair_stage_size < 0:
        raise ValueError("--add-repair-stage-size must be non-negative")
    if args.add_repair_adapter_size and args.add_repair_stage_size:
        raise ValueError("add only one repair adapter or repair stage per run")
    if args.add_play_hazard_adapter_size and not args.reset_optimizer:
        raise ValueError("--add-play-hazard-adapter-size requires --reset-optimizer")
    if args.add_placement_prior and not args.reset_optimizer:
        raise ValueError("--add-placement-prior requires --reset-optimizer")
    if args.add_public_history_slots and not args.reset_optimizer:
        raise ValueError("--add-public-history-slots requires --reset-optimizer")
    if args.trainable_prefix and not args.reset_optimizer:
        raise ValueError("--trainable-prefix requires --reset-optimizer")
    anchor_regularization = (
        args.anchor_l2_coef > 0.0
        or args.anchor_policy_kl_coef > 0.0
        or args.anchor_rehearsal_coef > 0.0
    )
    if bool(args.anchor_checkpoint) != anchor_regularization:
        raise ValueError(
            "--anchor-checkpoint requires a positive anchor regularization "
            "coefficient and vice versa"
        )
    if args.opponent_mode == "checkpoint" and not args.opponent_checkpoint:
        raise ValueError("--opponent-mode checkpoint requires --opponent-checkpoint")
    if args.opponent_mode != "checkpoint" and args.opponent_checkpoint:
        raise ValueError("--opponent-checkpoint requires --opponent-mode checkpoint")
    if args.opponent_mode == "strategy" and not args.opponent_strategy:
        raise ValueError("--opponent-mode strategy requires --opponent-strategy")
    if args.opponent_mode != "strategy" and args.opponent_strategy:
        raise ValueError("--opponent-strategy requires --opponent-mode strategy")
    if not 0.0 <= args.defense_scenario_probability <= 1.0:
        raise ValueError("--defense-scenario-probability must be between zero and one")
    if args.defense_scenario_probability > 0.0 and args.opponent_mode == "selfplay":
        raise ValueError("defense scenarios require a stationary opponent mode")
    if not (
        1
        <= args.defense_scenario_minimum_elixir
        <= args.defense_scenario_maximum_elixir
    ):
        raise ValueError("defense scenario elixir bounds are invalid")
    if args.defense_scenario_horizon_ticks <= 0:
        raise ValueError("defense scenario horizon must be positive")
    if args.defense_scenario_reward_scale < 0.0:
        raise ValueError("defense scenario reward scale must be non-negative")
    if args.opponent_mode == "league" and not (
        args.league_opponent or args.pfsp_report
    ):
        raise ValueError(
            "--opponent-mode league requires --league-opponent or --pfsp-report"
        )
    if args.opponent_mode != "league" and (
        args.league_opponent or args.pfsp_report or args.pfsp_strategy_workers
    ):
        raise ValueError("league/PFSP options require --opponent-mode league")
    if args.pfsp_strategy_workers is not None and not args.pfsp_report:
        raise ValueError("--pfsp-strategy-workers requires --pfsp-report")
    if (
        args.simulation_backend != "simple-pytorch"
        and args.opponent_mode in {"checkpoint", "league"}
        and args.actor_workers == 1
    ):
        raise ValueError(
            "checkpoint and league opponents currently require parallel actors"
        )
    if args.opponent_mode == "league" and args.league_opponent:
        league_kinds = set()
        for spec in args.league_opponent:
            if spec == "random":
                league_kinds.add("random")
            elif spec.startswith("strategy:"):
                strategy_name = spec.removeprefix("strategy:")
                if strategy_name not in STRATEGY_NAMES:
                    raise ValueError(f"unknown league strategy {strategy_name!r}")
                league_kinds.add("strategy")
            else:
                league_kinds.add("checkpoint")
    if args.d_model % args.num_heads != 0:
        raise ValueError("d_model must be divisible by num_heads")

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    if args.torch_threads is not None and args.torch_threads < 1:
        raise ValueError("--torch-threads must be positive")
    torch.set_num_threads(args.torch_threads or max(1, min(8, torch.get_num_threads())))
    learner_device = resolve_learner_device(args.device)
    actor_device = resolve_torch_device(args.actor_device)
    if (
        args.actor_workers > 1
        and actor_device.type != "cpu"
        and args.rollout_inference != "learner"
    ):
        raise ValueError(
            "parallel rollout workers currently require --actor-device cpu"
        )
    if args.rollout_inference == "learner" and (
        args.simulation_backend != "python"
        or args.opponent_mode not in {"noop", "random", "strategy"}
        or args.online_strategy_teacher is not None
    ):
        raise ValueError(
            "learner-side inference supports the scalar backend with noop, random, "
            "strategy or council opponents and no online teacher"
        )
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    sampling_decks_path = (
        resolve_decks_path(args.sampling_decks_path, must_exist=True)
        if args.sampling_decks_path is not None
        else decks_path
    )
    learner_sampling_decks_path = (
        resolve_decks_path(args.learner_sampling_decks_path, must_exist=True)
        if args.learner_sampling_decks_path is not None
        else sampling_decks_path
    )
    opponent_sampling_decks_path = (
        resolve_decks_path(args.opponent_sampling_decks_path, must_exist=True)
        if args.opponent_sampling_decks_path is not None
        else sampling_decks_path
    )
    matchups_path = (
        resolve_decks_path(args.matchups_path, must_exist=True)
        if args.matchups_path is not None
        else None
    )
    if not 0.0 <= args.matchup_probability <= 1.0:
        raise ValueError("--matchup-probability must be between zero and one")
    if (matchups_path is None) != (args.matchup_probability == 0.0):
        raise ValueError(
            "--matchups-path and a positive --matchup-probability must be used together"
        )
    if matchups_path is not None and args.opponent_mode == "selfplay":
        raise ValueError("exact matchup curricula require a stationary opponent mode")
    if matchups_path is not None and args.mirror_match:
        raise ValueError("exact matchup curricula are incompatible with --mirror-match")
    if args.opponent_mode == "selfplay" and (
        args.learner_sampling_decks_path is not None
        or args.opponent_sampling_decks_path is not None
    ):
        raise ValueError(
            "asymmetric learner/opponent deck pools require a stationary opponent mode"
        )
    opponent_checkpoints = tuple(
        str(resolve_path(path, must_exist=True)) for path in args.opponent_checkpoint
    )
    league_opponents = tuple(
        ("random", None)
        if spec == "random"
        else (
            ("strategy", spec.removeprefix("strategy:"))
            if spec.startswith("strategy:")
            else ("checkpoint", str(resolve_path(spec, must_exist=True)))
        )
        for spec in args.league_opponent
    )
    if args.pfsp_report:
        report_path = resolve_path(args.pfsp_report, must_exist=True)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report_weights = report.get("pfsp", {}).get("weights")
        if not isinstance(report_weights, dict):
            raise ValueError("--pfsp-report has no pfsp.weights object")
        simple_matchup_slots = args.num_envs // 2
        if args.simulation_backend == "simple-pytorch" and args.num_envs % 2:
            raise ValueError("simple league requires an even number of environments")
        strategy_workers = (
            args.pfsp_strategy_workers
            if args.pfsp_strategy_workers is not None
            else (
                simple_matchup_slots - len(league_opponents)
                if args.simulation_backend == "simple-pytorch"
                else args.actor_workers - len(league_opponents)
            )
        )
        if strategy_workers <= 0:
            raise ValueError("PFSP strategy allocation has no remaining worker slots")
        strategy_names = allocate_pfsp_slots(report_weights, strategy_workers)
        league_opponents += tuple(("strategy", name) for name in strategy_names)
    if args.opponent_mode == "league" and args.simulation_backend == "simple-pytorch":
        if args.num_envs % 2:
            raise ValueError("simple league requires an even number of environments")
        if len(league_opponents) > args.num_envs // 2:
            raise ValueError(
                "simple league opponent slots exceed paired matchup rows"
            )
        if len(set(league_opponents)) < 2:
            raise ValueError("simple league requires at least two distinct opponents")
        checkpoint_paths = {
            path
            for kind, path in league_opponents
            if kind == "checkpoint" and path is not None
        }
        if len(checkpoint_paths) > 1:
            raise ValueError(
                "simple-pytorch league supports one unique checkpoint policy"
            )
    if args.opponent_mode == "league" and args.simulation_backend != "simple-pytorch":
        if len(league_opponents) > args.actor_workers:
            raise ValueError("league opponent slots cannot exceed actor workers")
        kinds = {kind for kind, _ in league_opponents}
        if len(kinds) < 2:
            raise ValueError("league mode requires at least two opponent kinds")
    directory = checkpoints_dir(args.checkpoint_dir, create=True)
    resume, resume_path = _load_resume_state(args, directory, learner_device)
    initial_policy, initial_policy_path = _load_initial_policy_state(
        args, learner_device
    )

    token_names = resume.get("token_names") if resume is not None else None
    if args.simulation_backend == "simple-pytorch":
        from .simple_pytorch_backend import load_current_client_typed_vocabulary

        token_names = load_current_client_typed_vocabulary(
            resolve_path(args.simple_token_vocabulary_path, must_exist=True)
        ).token_names
    resume_config = (
        PolicyConfig.from_dict(resume["model_config"]) if resume is not None else None
    )
    initial_policy_config: PolicyConfig | None = None
    if initial_policy is not None and args.simulation_backend == "python":
        # Council path (see _load_initial_policy_state). The run vocabulary is
        # the builder's own; the checkpoint's contract, vocabulary, provenance
        # and weights are all checked against it in the council block below
        # before any environment exists.
        initial_policy_config = PolicyConfig.from_dict(initial_policy["model_config"])
        if initial_policy_config.public_contract_version != 4:
            raise ValueError("council initial policy is not a public-v4 actor")
    elif initial_policy is not None:
        if token_names is None:
            raise ValueError("initial policy requires an explicit run vocabulary")
        initial_policy_config = _validate_simple_initial_policy_contract(
            initial_policy,
            token_names=tuple(str(name) for name in token_names),
            max_entities=args.simple_max_entities,
        )
    if args.preflight_no_update:
        if args.resume_from or args.resume_latest:
            raise ValueError("launch preflight never resumes a run")
        if args.preflight_rollout_steps is not None and args.preflight_rollout_steps <= 0:
            raise ValueError("--preflight-rollout-steps must be positive")
        if (
            args.preflight_report_json is not None
            and Path(args.preflight_report_json).exists()
        ):
            raise FileExistsError("refusing to overwrite a preflight report")
    elif args.preflight_rollout_steps is not None or args.preflight_report_json:
        raise ValueError("preflight options require --preflight-no-update")
    base_config = resume_config or initial_policy_config
    if args.fresh_factorized_action_head:
        if base_config is not None:
            raise ValueError(
                "--fresh-factorized-action-head cannot modify an existing policy"
            )
        if args.card_semantics_version not in {3, 4}:
            raise ValueError(
                "--fresh-factorized-action-head requires card semantics v3 or v4"
            )
        if args.memory_kind != "structured":
            raise ValueError(
                "--fresh-factorized-action-head requires structured memory"
            )
    canonical_lane_globals = _canonical_lane_globals_for_run(
        actor_observation_domain=args.actor_observation_domain,
        resume_config=base_config,
        simulation_backend=args.simulation_backend,
    )
    public_contract_version = (
        base_config.public_contract_version
        if base_config
        else args.public_contract_version
    )
    if args.total_decisions is not None and args.total_decisions <= 0:
        raise ValueError("--total-decisions must be positive")
    if any(value <= 0 for value in args.checkpoint_decisions):
        raise ValueError("checkpoint decision counts must be positive")
    if public_contract_version >= 4 and args.reward_potential_scale is None:
        args.reward_potential_scale = 0.05
    args.max_ticks = resolve_match_horizon(args.max_ticks, public_contract_version)
    if public_contract_version >= 4:
        canonical_lane_globals = True
        if args.simulation_backend != "python":
            raise ValueError("council public contract requires the scalar backend")
    target_public_history_slots = (
        args.add_public_history_slots
        if args.add_public_history_slots
        else (
            base_config.public_history_slots
            if base_config
            else args.public_history_slots
        )
    )
    # Deterministic-state training needs one exact teacher event pulse.  This
    # does not change the model's public-history input contract: the adapter
    # below converts simulator history to a current-frame event before forward.
    teacher_public_history_slots = max(
        target_public_history_slots,
        int(
            args.enable_structured_deterministic_resource
            or (
                resume_config is not None
                and resume_config.structured_deterministic_resource_enabled
            )
        ),
    )
    target_public_seen_card_slots = (
        args.add_public_seen_card_slots
        if args.add_public_seen_card_slots
        else (
            base_config.public_seen_card_slots
            if base_config
            else args.public_seen_card_slots
        )
    )
    builder = StructuredObservationBuilder(
        decks_path=decks_path,
        max_entities=(
            base_config.max_entities
            if base_config is not None
            else (
                args.simple_max_entities
                if args.simulation_backend == "simple-pytorch"
                else 128
            )
        ),
        token_names=token_names,
        card_semantics_version=(
            base_config.card_semantics_version
            if base_config is not None
            else args.card_semantics_version
        ),
        canonical_lane_globals=canonical_lane_globals,
        public_history_slots=teacher_public_history_slots,
        public_seen_card_slots=target_public_seen_card_slots,
        public_entity_levels=public_contract_version >= 3,
        public_hand_levels=public_contract_version >= 4,
    )
    if args.add_repair_adapter_size and resume_config is None:
        raise ValueError("--add-repair-adapter-size requires a resumed checkpoint")
    if args.add_action_type_adapter and resume_config is None:
        raise ValueError("--add-action-type-adapter requires a resumed checkpoint")
    if args.add_structured_resource_policy_gate and resume_config is None:
        raise ValueError(
            "--add-structured-resource-policy-gate requires a resumed checkpoint"
        )
    if args.enable_structured_deterministic_resource and resume_config is None:
        raise ValueError(
            "--enable-structured-deterministic-resource requires a resumed checkpoint"
        )
    if args.add_repair_stage_size and resume_config is None:
        raise ValueError("--add-repair-stage-size requires a resumed checkpoint")
    if args.add_placement_prior and resume_config is None:
        raise ValueError("--add-placement-prior requires a resumed checkpoint")
    if args.add_public_history_slots and resume_config is None:
        raise ValueError("--add-public-history-slots requires a resumed checkpoint")
    if args.add_public_seen_card_slots and resume_config is None:
        raise ValueError("--add-public-seen-card-slots requires a resumed checkpoint")
    if args.add_public_seen_card_slots and target_public_history_slots <= 0:
        raise ValueError("public seen-card slots require public history slots")
    if (
        args.add_public_history_slots
        and resume_config is not None
        and resume_config.public_history_slots > 0
    ):
        raise ValueError("resumed checkpoint already has public history")
    if (
        args.add_public_seen_card_slots
        and resume_config is not None
        and resume_config.public_seen_card_slots > 0
    ):
        raise ValueError("resumed checkpoint already has public seen-card memory")
    if (
        args.add_placement_prior
        and resume_config is not None
        and resume_config.placement_prior_enabled
    ):
        raise ValueError("resumed checkpoint already has a placement prior")
    if (
        args.add_action_type_adapter
        and resume_config is not None
        and resume_config.action_type_adapter_enabled
    ):
        raise ValueError("resumed checkpoint already has an action-type adapter")
    if args.add_structured_resource_policy_gate and resume_config is not None:
        if resume_config.memory_kind != "structured":
            raise ValueError(
                "structured resource policy gate requires structured memory"
            )
        if resume_config.structured_resource_policy_gate_enabled:
            raise ValueError("resumed checkpoint already has a resource policy gate")
    if args.enable_structured_deterministic_resource and resume_config is not None:
        if resume_config.memory_kind != "structured":
            raise ValueError(
                "structured deterministic resource requires structured memory"
            )
        if resume_config.structured_deterministic_resource_enabled:
            raise ValueError(
                "resumed checkpoint already has deterministic resource tracking"
            )
    if (
        args.add_repair_adapter_size
        and resume_config is not None
        and resume_config.repair_adapter_size > 0
    ):
        raise ValueError("resumed checkpoint already has a dense repair adapter")
    if args.add_play_hazard_adapter_size and resume_config is None:
        raise ValueError("play hazard adapter requires a resumed checkpoint")
    if (
        args.add_play_hazard_adapter_size
        and resume_config is not None
        and resume_config.play_hazard_adapter_size > 0
    ):
        raise ValueError("resumed checkpoint already has a play hazard adapter")
    config = base_config or PolicyConfig(
        public_contract_version=public_contract_version,
        public_token_names=builder.token_names if public_contract_version >= 2 else (),
        public_history_slots=target_public_history_slots,
        public_seen_card_slots=target_public_seen_card_slots,
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.spec.max_entities,
        card_semantics_version=args.card_semantics_version,
        public_observation_confidence=(
            public_contract_version >= 4
            or args.actor_observation_domain in {"causal-vision-v1", "causal-frame-v1"}
        ),
        actor_observation_domain=args.actor_observation_domain,
        canonical_lane_globals=canonical_lane_globals,
        d_model=args.d_model,
        num_heads=args.num_heads,
        actor_layers=args.actor_layers,
        critic_layers=args.critic_layers,
        memory_size=args.memory_size,
        encoder_kind=args.encoder_kind,
        decoder_kind=args.decoder_kind,
        memory_kind=args.memory_kind,
        card_input_mode=args.card_input_mode,
        action_value_head_enabled=args.action_value_head,
        deterministic_hierarchy=(
            "play-gate" if args.fresh_factorized_action_head else "slot"
        ),
        hierarchical_mode_gate_enabled=args.fresh_factorized_action_head,
        semantic_slot_choice_adapter_enabled=args.fresh_factorized_action_head,
        semantic_slot_choice_replace_base=args.fresh_factorized_action_head,
        mechanics_slot_choice_adapter_enabled=args.fresh_factorized_action_head,
        mechanics_slot_choice_replace_base=args.fresh_factorized_action_head,
        actor_current_hand_slot_invariant=args.fresh_factorized_action_head,
        equivariant_slot_choice=args.fresh_factorized_action_head,
    )
    added_action_value_to_initial = bool(
        initial_policy is not None
        and args.action_value_head
        and not config.action_value_head_enabled
    )
    if added_action_value_to_initial:
        config = replace(config, action_value_head_enabled=True)
    if config.action_value_head_enabled != (args.action_value_coef > 0.0):
        raise ValueError(
            "fresh action-value head and a positive action-value coefficient "
            "must be enabled together"
        )
    if args.add_repair_adapter_size:
        config = replace(config, repair_adapter_size=args.add_repair_adapter_size)
    if args.add_play_hazard_adapter_size:
        config = replace(
            config,
            play_hazard_adapter_size=args.add_play_hazard_adapter_size,
            play_hazard_adapter_enemy_y_gate=(
                args.play_hazard_adapter_enemy_y_gate
            ),
        )
    if args.hazard_conditioned_rollouts and not config.play_hazard_enabled:
        raise ValueError("hazard-conditioned rollouts require a play-hazard policy")
    if args.add_action_type_adapter:
        config = replace(config, action_type_adapter_enabled=True)
    if args.add_structured_resource_policy_gate:
        config = replace(config, structured_resource_policy_gate_enabled=True)
    if args.enable_structured_deterministic_resource:
        config = replace(config, structured_deterministic_resource_enabled=True)
    if args.add_placement_prior:
        config = replace(config, placement_prior_enabled=True)
    if args.add_public_history_slots:
        config = replace(
            config,
            public_history_slots=args.add_public_history_slots,
        )
    if args.add_public_seen_card_slots:
        config = replace(
            config,
            public_seen_card_slots=args.add_public_seen_card_slots,
        )
    added_stage_index: int | None = None
    if args.add_repair_stage_size:
        added_stage_index = len(config.repair_stage_sizes)
        config = replace(
            config,
            repair_stage_sizes=(
                *config.repair_stage_sizes,
                args.add_repair_stage_size,
            ),
        )
    council_initialization: dict[str, Any] | None = None
    preflight_admission: str | None = None
    if initial_policy is not None and args.simulation_backend == "python" and (
        config.public_contract_version < 4
    ):
        raise ValueError("python-backend initialization is gated to the council path")
    if config.public_contract_version >= 4:
        from .council_pilot import (
            load_pilot_config,
            require_pilot_admission,
            validate_council_trainer_args,
        )

        if args.council_config is None or args.council_admission is None:
            raise ValueError(
                "council gameplay fitting requires a pinned config and Tier A admission receipt"
            )
        pilot_config = load_pilot_config(args.council_config)
        validate_council_trainer_args(pilot_config, args, config, builder)
        levels = (
            (10, 11, 12)
            if (
                args.level_randomization_after is not None
                and args.total_decisions is not None
                and args.total_decisions > args.level_randomization_after
            )
            else (11,)
        )
        if args.preflight_no_update:
            # A launch preflight never steps the optimizer and writes no
            # checkpoint, so it is not gameplay fitting and does not consume a
            # Tier A receipt. Source pins are still verified; the admission
            # file is used only as the digest the initializer must carry.
            from .council_pilot import load_source_pins

            load_source_pins(pilot_config)
            preflight_admission = "not-checked-preflight-no-update"
        else:
            require_pilot_admission(
                pilot_config, args.council_admission, levels=levels
            )
            preflight_admission = None
        from .council_budget import require_owned_budget
        require_owned_budget(args.council_budget_ledger)
        if initial_policy is not None:
            from .council_pilot import (
                is_continuation,
                is_human_prior,
                validate_council_continuation,
                validate_council_human_prior,
                validate_council_initial_policy,
            )

            assert initial_policy_path is not None
            # Three initializer paths: the declared continuation, the declared
            # human prior (research artifact; scripted-arm slot), otherwise the
            # admission-bound warm-start / random-control check.
            validate_initializer = (
                validate_council_continuation
                if is_continuation(pilot_config, args.seed, args.council_arm)
                else validate_council_human_prior
                if is_human_prior(pilot_config, args.seed, args.council_arm)
                else validate_council_initial_policy
            )
            council_initialization = validate_initializer(
                pilot_config,
                initial_policy,
                initialization_path=initial_policy_path,
                args=args,
                builder=builder,
            )
        source_checkpoint = resume if resume is not None else initial_policy
        if (
            source_checkpoint is not None
            and source_checkpoint.get("gamedata_sha256") != pilot_config.gamedata_sha256
        ):
            raise ValueError(
                "council checkpoint ruleset differs from the admitted runtime"
            )
        if resume is not None and resume.get("council_config_sha256") != _sha256(
            args.council_config
        ):
            raise ValueError("resumed council run has a different pilot configuration")
        if resume is not None and initial_policy is None:
            from .council_pilot import is_human_prior

            if is_human_prior(pilot_config, args.seed, args.council_arm):
                # Keep the human-prior initialization record (research-artifact
                # status included) in every later checkpoint of the run.
                carried = resume.get("council_initialization") or {}
                if (
                    carried.get("initialization") != "human_prior"
                    or carried.get("sha256")
                    != pilot_config.human_prior_checkpoint_sha256
                ):
                    raise ValueError(
                        "resumed human-prior run lost its declared initialization record"
                    )
                council_initialization = carried
    model = ClasherPolicy(config, builder.card_stat_features).to(learner_device)
    if config.public_contract_version >= 4 and source_checkpoint is not None:
        for name, value in model.state_dict().items():
            if name.endswith(
                ("card_stat_features", "semantic_card_features")
            ) and not torch.equal(
                value.cpu(), source_checkpoint["model_state_dict"][name].cpu()
            ):
                raise ValueError(
                    "council checkpoint semantic buffers differ from the bound ruleset"
                )
    if actor_device == learner_device:
        actor_model = model
    else:
        actor_model = ClasherPolicy(config, builder.card_stat_features).to(actor_device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, eps=1e-5, weight_decay=1e-5
    )
    start_update = 1
    total_transitions = 0
    if resume is not None:
        incompatible = model.load_state_dict(
            resume["model_state_dict"],
            strict=not bool(
                args.add_placement_prior
                or args.add_public_history_slots
                or args.add_action_type_adapter
                or args.add_structured_resource_policy_gate
                or args.add_repair_adapter_size
                or args.add_repair_stage_size
                or args.add_play_hazard_adapter_size
            ),
        )
        if args.add_placement_prior and (
            incompatible.unexpected_keys
            or incompatible.missing_keys != ["placement_prior.weight"]
        ):
            raise ValueError(
                "only placement-prior parameters may be absent while resuming"
            )
        if args.add_public_history_slots:
            if incompatible.unexpected_keys or not incompatible.missing_keys:
                raise ValueError(
                    "unexpected checkpoint mismatch while adding public history"
                )
            if not all(
                name.startswith("public_history_") for name in incompatible.missing_keys
            ):
                raise ValueError(
                    "only public-history parameters may be absent while resuming"
                )
        if args.add_action_type_adapter and (
            incompatible.unexpected_keys
            or not incompatible.missing_keys
            or not all(
                name.startswith("action_type_adapter.")
                for name in incompatible.missing_keys
            )
        ):
            raise ValueError(
                "only action-type-adapter parameters may be absent while resuming"
            )
        if args.add_structured_resource_policy_gate and (
            incompatible.unexpected_keys
            or incompatible.missing_keys != ["structured_resource_policy_gate"]
        ):
            raise ValueError(
                "only the structured resource policy gate may be absent while resuming"
            )
        if args.add_repair_adapter_size:
            if incompatible.unexpected_keys or not incompatible.missing_keys:
                raise ValueError("unexpected checkpoint mismatch while adding adapter")
            if not all(
                name.startswith("repair_adapter.") for name in incompatible.missing_keys
            ):
                raise ValueError(
                    "only dense repair-adapter parameters may be absent while resuming"
                )
        if args.add_play_hazard_adapter_size and (
            incompatible.unexpected_keys
            or not incompatible.missing_keys
            or not all(
                name.startswith("play_hazard_adapter.")
                for name in incompatible.missing_keys
            )
        ):
            raise ValueError(
                "only play-hazard-adapter parameters may be absent while resuming"
            )
        if args.add_repair_stage_size:
            assert added_stage_index is not None
            expected_prefix = f"repair_stages.{added_stage_index}."
            if incompatible.unexpected_keys or not incompatible.missing_keys:
                raise ValueError("unexpected checkpoint mismatch while adding stage")
            if not all(
                name.startswith(expected_prefix) for name in incompatible.missing_keys
            ):
                raise ValueError(
                    "only the appended repair-stage parameters may be absent while "
                    "resuming"
                )
        if "optimizer_state_dict" in resume and not args.reset_optimizer:
            restore_optimizer_state(
                optimizer,
                resume["optimizer_state_dict"],
                learning_rate=args.learning_rate,
            )
        start_update = int(resume.get("update", 0)) + 1
        total_transitions = int(resume.get("total_transitions", 0))
    elif initial_policy is not None:
        incompatible = model.load_state_dict(
            initial_policy["model_state_dict"],
            strict=not added_action_value_to_initial,
        )
        if added_action_value_to_initial and (
            incompatible.unexpected_keys
            or not incompatible.missing_keys
            or not all(
                name == "action_value_policy_gate"
                or name.startswith("action_value_head.")
                for name in incompatible.missing_keys
            )
        ):
            raise ValueError(
                "only action-value parameters may be absent from the initializer"
            )
        if council_initialization is not None:
            from .council_pilot import require_initialized_weights

            # Strict load plus an exact post-load digest: no key, dtype, shape
            # or byte of the published initializer may differ in the learner.
            require_initialized_weights(model, council_initialization, optimizer)
    if args.trainable_prefix:
        prefixes = tuple(args.trainable_prefix)
        for name, parameter in model.named_parameters():
            parameter.requires_grad = name.startswith(prefixes)
        trainable_parameters = [
            parameter for parameter in model.parameters() if parameter.requires_grad
        ]
        if not trainable_parameters:
            raise ValueError("--trainable-prefix matched no model parameters")
        optimizer = torch.optim.AdamW(
            trainable_parameters,
            lr=args.learning_rate,
            eps=1e-5,
            weight_decay=1e-5,
        )
    anchor_parameters: tuple[Tensor | None, ...] | None = None
    anchor_model: ClasherPolicy | None = None
    anchor_path: Path | None = None
    if args.anchor_checkpoint:
        anchor_path = resolve_path(args.anchor_checkpoint, must_exist=True)
        anchor = torch.load(
            anchor_path, map_location=learner_device, weights_only=False
        )
        anchor_config = replace(
            PolicyConfig.from_dict(anchor["model_config"]),
            max_entities=config.max_entities,
        )
        compatible_zero_prior = (
            config.placement_prior_enabled
            and not anchor_config.placement_prior_enabled
            and replace(config, placement_prior_enabled=False) == anchor_config
        )
        compatible_zero_history = (
            config.public_history_slots > 0
            and anchor_config.public_history_slots == 0
            and anchor_config.public_seen_card_slots == 0
            and replace(
                config,
                public_history_slots=0,
                public_seen_card_slots=0,
            )
            == anchor_config
        )
        compatible_zero_action_type_adapter = (
            config.action_type_adapter_enabled
            and not anchor_config.action_type_adapter_enabled
            and replace(config, action_type_adapter_enabled=False) == anchor_config
        )
        compatible_zero_resource_gate = (
            config.structured_resource_policy_gate_enabled
            and not anchor_config.structured_resource_policy_gate_enabled
            and replace(config, structured_resource_policy_gate_enabled=False)
            == anchor_config
        )
        compatible_zero_repair_adapter = (
            config.repair_adapter_size > 0
            and anchor_config.repair_adapter_size == 0
            and replace(config, repair_adapter_size=0) == anchor_config
        )
        compatible_zero_hazard_adapter = (
            config.play_hazard_adapter_size > 0
            and anchor_config.play_hazard_adapter_size == 0
            and replace(
                config,
                play_hazard_adapter_size=0,
                play_hazard_adapter_enemy_y_gate=1.0,
            )
            == anchor_config
        )
        if (
            anchor_config != config
            and not compatible_zero_prior
            and not compatible_zero_history
            and not compatible_zero_action_type_adapter
            and not compatible_zero_resource_gate
            and not compatible_zero_repair_adapter
            and not compatible_zero_hazard_adapter
        ):
            raise ValueError(
                "anchor checkpoint model config does not match training model"
            )
        if tuple(anchor["token_names"]) != tuple(builder.token_names):
            raise ValueError(
                "anchor checkpoint token vocabulary does not match training model"
            )
        anchor_state = anchor["model_state_dict"]
        anchor_reference = ClasherPolicy(config, builder.card_stat_features).to(
            learner_device
        )
        anchor_incompatible = anchor_reference.load_state_dict(
            anchor_state,
            strict=not (
                compatible_zero_prior
                or compatible_zero_history
                or compatible_zero_action_type_adapter
                or compatible_zero_resource_gate
                or compatible_zero_repair_adapter
                or compatible_zero_hazard_adapter
            ),
        )
        if compatible_zero_prior and (
            anchor_incompatible.unexpected_keys
            or anchor_incompatible.missing_keys != ["placement_prior.weight"]
        ):
            raise ValueError("unexpected zero-prior anchor checkpoint mismatch")
        if compatible_zero_history and (
            anchor_incompatible.unexpected_keys
            or not anchor_incompatible.missing_keys
            or not all(
                name.startswith(PUBLIC_BELIEF_PARAMETER_PREFIXES)
                for name in anchor_incompatible.missing_keys
            )
        ):
            raise ValueError("unexpected zero-history anchor checkpoint mismatch")
        if compatible_zero_action_type_adapter and (
            anchor_incompatible.unexpected_keys
            or not anchor_incompatible.missing_keys
            or not all(
                name.startswith("action_type_adapter.")
                for name in anchor_incompatible.missing_keys
            )
        ):
            raise ValueError(
                "unexpected zero-action-type-adapter anchor checkpoint mismatch"
            )
        if compatible_zero_resource_gate and (
            anchor_incompatible.unexpected_keys
            or anchor_incompatible.missing_keys != ["structured_resource_policy_gate"]
        ):
            raise ValueError("unexpected zero-resource-gate anchor checkpoint mismatch")
        if compatible_zero_repair_adapter and (
            anchor_incompatible.unexpected_keys
            or not anchor_incompatible.missing_keys
            or not all(
                name.startswith("repair_adapter.")
                for name in anchor_incompatible.missing_keys
            )
        ):
            raise ValueError("unexpected zero-repair-adapter anchor checkpoint mismatch")
        if compatible_zero_hazard_adapter and (
            anchor_incompatible.unexpected_keys
            or not anchor_incompatible.missing_keys
            or not all(
                name.startswith("play_hazard_adapter.")
                for name in anchor_incompatible.missing_keys
            )
        ):
            raise ValueError("unexpected zero-hazard-adapter anchor checkpoint mismatch")
        anchor_parameters = tuple(
            parameter.detach().clone() if name in anchor_state else None
            for name, parameter in anchor_reference.named_parameters()
        )
        if args.anchor_policy_kl_coef > 0.0 or args.anchor_rehearsal_coef > 0.0:
            anchor_model = anchor_reference.eval()
            anchor_model.requires_grad_(False)
    rehearsal: PlacementRehearsal | None = None
    if args.rehearsal_corpus:
        rehearsal = PlacementRehearsal.load(
            resolve_path(args.rehearsal_corpus, must_exist=True),
            builder=builder,
            device=learner_device,
            sequence_length=(args.rehearsal_sequence_length or args.rollout_steps),
            seed=args.seed + 67_867,
            loss_component=args.rehearsal_loss_component,
        )
    causal_rehearsal: CausalDecisionRehearsal | None = None
    if args.causal_rehearsal_corpus:
        assert args.causal_rehearsal_public_sidecar is not None
        causal_rehearsal = CausalDecisionRehearsal.load(
            resolve_path(args.causal_rehearsal_corpus, must_exist=True),
            resolve_path(args.causal_rehearsal_public_sidecar, must_exist=True),
            token_names=tuple(builder.token_names),
            max_entities=builder.max_entities,
            sequence_length=(
                args.causal_rehearsal_sequence_length or args.rollout_steps
            ),
            seed=args.seed + 101_333,
        )
    causal_spatial_rehearsal: CausalDecisionRehearsal | None = None
    if args.causal_spatial_rehearsal_corpus:
        assert args.causal_spatial_rehearsal_public_sidecar is not None
        causal_spatial_rehearsal = CausalDecisionRehearsal.load(
            resolve_path(args.causal_spatial_rehearsal_corpus, must_exist=True),
            resolve_path(
                args.causal_spatial_rehearsal_public_sidecar,
                must_exist=True,
            ),
            token_names=tuple(builder.token_names),
            max_entities=builder.max_entities,
            sequence_length=(
                args.causal_spatial_rehearsal_sequence_length
                or args.rollout_steps
            ),
            seed=args.seed + 101_339,
        )
    anchor_rehearsal: PlacementRehearsal | None = None
    if args.anchor_rehearsal_corpus:
        anchor_rehearsal = PlacementRehearsal.load(
            resolve_path(args.anchor_rehearsal_corpus, must_exist=True),
            builder=builder,
            device=learner_device,
            sequence_length=(
                args.anchor_rehearsal_sequence_length or args.rollout_steps
            ),
            seed=args.seed + 81_211,
            loss_component=args.anchor_rehearsal_loss_component,
        )
    synchronize_actor_model(model, actor_model)

    # Fresh runs keep --seed; a resumed segment gets fresh environment, opponent
    # and actor-process streams and restores the learner RNG saved with its
    # checkpoint (just before the first update below).
    segments_path = directory / RUN_SEGMENTS_FILE
    segment_index = (
        sum(1 for line in segments_path.read_text().splitlines() if line.strip())
        if segments_path.exists()
        else 0
    )
    rollout_seed = (
        args.seed
        if resume is None
        else resume_rollout_seed(
            args.seed, start_update=start_update, segment=segment_index
        )
    )
    resume_rng: dict[str, Any] | None = None
    if resume is not None:
        assert resume_path is not None
        earlier_starts = (
            {
                json.loads(line).get("start_update")
                for line in segments_path.read_text().splitlines()
                if line.strip()
            }
            if segments_path.exists()
            else set()
        )
        # Restoring the same checkpoint's learner RNG twice would replay the
        # earlier continuation (e.g. games played after it before a crash), so
        # only the first resume from a given update restores; later ones reseed.
        if start_update not in earlier_starts:
            resume_rng = load_rng_state(
                resume_path.parent, checkpoint=resume_path, update=start_update - 1
            )

    envs: list[SelfPlayBattleEnv] = []
    parallel_collector: Any = None
    batched_collector: Any = None
    simple_collector: Any = None
    simulation_backend_metadata: dict[str, Any] | None = None
    learner_teacher_balanced_config: BalancedStrategyConfig | None = None
    if args.online_strategy_teacher_balanced_config is not None:
        teacher_config_path = resolve_path(
            args.online_strategy_teacher_balanced_config,
            must_exist=True,
        )
        teacher_config_payload = json.loads(
            teacher_config_path.read_text(encoding="utf-8")
        )
        if not isinstance(teacher_config_payload, dict):
            raise TypeError("online balanced teacher config must be an object")
        learner_teacher_balanced_config = BalancedStrategyConfig(
            **teacher_config_payload
        )
    learner_teacher_bot = (
        StrategyBot(
            args.online_strategy_teacher,
            balanced_config=(
                learner_teacher_balanced_config or BalancedStrategyConfig()
            ),
        )
        if args.online_strategy_teacher is not None
        else None
    )
    if args.simulation_backend == "simple-pytorch":
        from .simple_pytorch_backend import SimplePytorchTrainingCollector
        simple_opponent_model: ClasherPolicy | None = None
        simple_opponent_sha256: str | None = None
        simple_checkpoint_path: Path | None = None
        if args.opponent_mode == "checkpoint":
            simple_checkpoint_path = Path(opponent_checkpoints[0])
        elif args.opponent_mode == "league":
            simple_checkpoint_paths: set[str] = {
                path
                for kind, path in league_opponents
                if kind == "checkpoint" and path is not None
            }
            if simple_checkpoint_paths:
                simple_checkpoint_path = Path(next(iter(simple_checkpoint_paths)))
        if simple_checkpoint_path is not None:
            from .parallel_rollout import load_checkpoint_opponent

            simple_opponent_model = load_checkpoint_opponent(
                simple_checkpoint_path,
                device=actor_device,
                builder=builder,
                learner_config=config,
                token_names=tuple(builder.token_names),
            )
            simple_opponent_sha256 = _sha256(simple_checkpoint_path)

        simple_collector = SimplePytorchTrainingCollector(
            model=actor_model,
            builder=builder,
            batch_size=args.num_envs,
            device=actor_device,
            decision_interval=args.decision_interval,
            gamma=args.gamma,
            supported_decks_path=resolve_path(
                args.simple_supported_decks_path, must_exist=True
            ),
            typed_vocabulary_path=resolve_path(
                args.simple_token_vocabulary_path, must_exist=True
            ),
            mirror_match=args.mirror_match,
            opponent_mode=args.opponent_mode,
            opponent_model=simple_opponent_model,
            opponent_checkpoint_sha256=simple_opponent_sha256,
            opponent_strategy=(
                args.opponent_strategy
                if args.opponent_mode == "strategy"
                else None
            ),
            opponent_strategy_schedule=(
                tuple(
                    str(path)
                    for kind, path in league_opponents
                    if kind == "strategy" and path is not None
                )
                if args.opponent_mode == "league"
                else ()
            ),
            opponent_league_schedule=(
                cast(
                    tuple[
                        tuple[
                            Literal["random", "strategy", "checkpoint"],
                            str | None,
                        ],
                        ...,
                    ],
                    league_opponents,
                )
                if args.opponent_mode == "league"
                else ()
            ),
            learner_deck_name=args.simple_learner_deck_name,
            checkpoint_opponent_deck_name=(
                args.simple_checkpoint_opponent_deck_name
            ),
            learner_teacher_strategy=args.online_strategy_teacher,
            learner_teacher_balanced_config=(
                learner_teacher_balanced_config
            ),
            learner_sampling_temperature=(
                args.simple_learner_sampling_temperature
            ),
            max_effects=args.simple_max_effects,
        )
        simulation_backend_metadata = simple_collector.checkpoint_metadata()
        simulation_backend_metadata["collector_actor_projection_domain"] = (
            "simulator-exact-public"
        )
        simulation_backend_metadata["policy_actor_observation_domain"] = (
            model.config.actor_observation_domain
        )
        if initial_policy_path is not None:
            assert initial_policy is not None
            source_policy_config = PolicyConfig.from_dict(
                initial_policy["model_config"]
            )
            simulation_backend_metadata["initial_policy"] = {
                "path": str(initial_policy_path),
                "sha256": _sha256(initial_policy_path),
                "weights_only": True,
                "source_max_entities": source_policy_config.max_entities,
                "runtime_max_entities": config.max_entities,
                "entity_capacity_rebound": (
                    source_policy_config.max_entities != config.max_entities
                ),
                "optimizer_reset": True,
                "update_reset": True,
                "simulator_state_reset": True,
            }
    elif args.rollout_inference == "learner":
        from .parallel_rollout import (
            ActorWorkerConfig,
            BatchedInferenceCollector,
            OpponentSpec,
        )

        learner_opponent_pool: tuple[OpponentSpec, ...] = (
            (OpponentSpec(kind="strategy", strategy=args.opponent_strategy),)
            if args.opponent_mode == "strategy"
            else (OpponentSpec(kind=args.opponent_mode),)
        )
        batched_collector = BatchedInferenceCollector.with_actor_processes(
            num_workers=args.actor_workers,
            num_envs=args.num_envs,
            builder=builder,
            config=ActorWorkerConfig(
                decks_path=str(decks_path),
                token_names=builder.token_names,
                model_config=config.to_dict(),
                recurrent_update_mode=getattr(args, "recurrent_update_mode", "full-prefix"),
                tbptt_burn_in=getattr(args, "tbptt_burn_in", 16),
                decision_interval=args.decision_interval,
                max_ticks=args.max_ticks,
                mirror_match=args.mirror_match,
                opponent_mode=args.opponent_mode,
                opponent_pool=learner_opponent_pool,
                engine_fast_path=args.engine_fast_path,
                quiet_engine=args.quiet_engine,
                base_seed=rollout_seed,
                torch_threads=args.actor_threads,
                reward_profile=args.reward_profile,
                reward_potential_scale=args.reward_potential_scale,
                level_randomization_after=args.level_randomization_after,
                mixed_level_probability=args.mixed_level_probability,
                initial_learner_decisions=total_transitions,
                council_opponent_pool=str(args.council_opponent_pool)
                if args.council_opponent_pool is not None
                else None,
                reward_shaping_gamma=args.reward_shaping_gamma,
                elixir_leak_penalty_scale=args.elixir_leak_penalty_scale,
                defense_scenario_probability=args.defense_scenario_probability,
                defense_scenario_minimum_elixir=(args.defense_scenario_minimum_elixir),
                defense_scenario_maximum_elixir=(args.defense_scenario_maximum_elixir),
                defense_scenario_horizon_ticks=args.defense_scenario_horizon_ticks,
                defense_scenario_reward_scale=args.defense_scenario_reward_scale,
                sampling_decks_path=str(sampling_decks_path),
                learner_sampling_decks_path=str(learner_sampling_decks_path),
                opponent_sampling_decks_path=str(opponent_sampling_decks_path),
                matchups_path=str(matchups_path) if matchups_path is not None else None,
                matchup_probability=args.matchup_probability,
                trim_rollout_entity_padding=args.trim_rollout_entity_padding,
                hazard_conditioned_rollouts=args.hazard_conditioned_rollouts,
            ),
        )
        atexit.register(batched_collector.close)
    elif args.actor_workers == 1:
        with maybe_silence_stdio(args.quiet_engine):
            for index in range(args.num_envs):
                learner_player = index % 2
                player_sampling_paths = (
                    (learner_sampling_decks_path, opponent_sampling_decks_path)
                    if learner_player == 0
                    else (opponent_sampling_decks_path, learner_sampling_decks_path)
                )
                env = SelfPlayBattleEnv(
                    public_contract_version=config.public_contract_version,
                    level_randomization_after=args.level_randomization_after,
                    mixed_level_probability=args.mixed_level_probability,
                    reward_potential_scale=args.reward_potential_scale,
                    decision_interval_ticks=args.decision_interval,
                    max_ticks=args.max_ticks,
                    decks_path=decks_path,
                    sampling_decks_path=sampling_decks_path,
                    player0_sampling_decks_path=player_sampling_paths[0],
                    player1_sampling_decks_path=player_sampling_paths[1],
                    matchups_path=matchups_path,
                    matchup_probability=args.matchup_probability,
                    learner_player_id=learner_player,
                    seed=rollout_seed + index * 1009,
                    mirror_match=args.mirror_match,
                    canonical_perspective=True,
                    canonical_lane_globals=config.canonical_lane_globals,
                    engine_fast_path=args.engine_fast_path,
                    reward_profile=args.reward_profile,
                    reward_shaping_gamma=args.reward_shaping_gamma,
                    elixir_leak_penalty_scale=args.elixir_leak_penalty_scale,
                    defense_scenario_probability=args.defense_scenario_probability,
                    defense_scenario_minimum_elixir=(
                        args.defense_scenario_minimum_elixir
                    ),
                    defense_scenario_maximum_elixir=(
                        args.defense_scenario_maximum_elixir
                    ),
                    defense_scenario_horizon_ticks=(
                        args.defense_scenario_horizon_ticks
                    ),
                    defense_scenario_reward_scale=(args.defense_scenario_reward_scale),
                )
                env._structured_obs_builder = builder
                env.set_learner_decisions(total_transitions)
                env.reset(seed=rollout_seed + index * 1009)
                envs.append(env)
    else:
        from .parallel_rollout import (
            ActorWorkerConfig,
            OpponentSpec,
            ParallelRolloutCollector,
        )

        opponent_pool: tuple[OpponentSpec, ...]
        if args.opponent_mode == "noop":
            opponent_pool = (OpponentSpec(kind="noop"),)
        elif args.opponent_mode == "random":
            opponent_pool = (OpponentSpec(kind="random"),)
        elif args.opponent_mode == "strategy":
            opponent_pool = (
                OpponentSpec(kind="strategy", strategy=args.opponent_strategy),
            )
        elif args.opponent_mode == "checkpoint":
            opponent_pool = tuple(
                OpponentSpec(kind="checkpoint", checkpoint=path)
                for path in opponent_checkpoints
            )
        elif args.opponent_mode == "league":
            opponent_pool = tuple(
                (
                    OpponentSpec(kind="random")
                    if kind == "random"
                    else (
                        OpponentSpec(kind="strategy", strategy=path)
                        if kind == "strategy"
                        else OpponentSpec(kind="checkpoint", checkpoint=path)
                    )
                )
                for kind, path in league_opponents
            )
        else:
            opponent_pool = ()

        parallel_collector = ParallelRolloutCollector(
            num_workers=args.actor_workers,
            num_envs=args.num_envs,
            config=ActorWorkerConfig(
                decks_path=str(decks_path),
                token_names=builder.token_names,
                model_config=config.to_dict(),
                recurrent_update_mode=getattr(args, "recurrent_update_mode", "full-prefix"),
                tbptt_burn_in=getattr(args, "tbptt_burn_in", 16),
                decision_interval=args.decision_interval,
                max_ticks=args.max_ticks,
                mirror_match=args.mirror_match,
                opponent_mode=args.opponent_mode,
                opponent_pool=opponent_pool,
                engine_fast_path=args.engine_fast_path,
                quiet_engine=args.quiet_engine,
                base_seed=rollout_seed,
                torch_threads=args.actor_threads,
                reward_profile=args.reward_profile,
                reward_potential_scale=args.reward_potential_scale,
                level_randomization_after=args.level_randomization_after,
                mixed_level_probability=args.mixed_level_probability,
                initial_learner_decisions=total_transitions,
                council_opponent_pool=str(args.council_opponent_pool)
                if args.council_opponent_pool is not None
                else None,
                reward_shaping_gamma=args.reward_shaping_gamma,
                elixir_leak_penalty_scale=args.elixir_leak_penalty_scale,
                defense_scenario_probability=args.defense_scenario_probability,
                defense_scenario_minimum_elixir=(args.defense_scenario_minimum_elixir),
                defense_scenario_maximum_elixir=(args.defense_scenario_maximum_elixir),
                defense_scenario_horizon_ticks=args.defense_scenario_horizon_ticks,
                defense_scenario_reward_scale=args.defense_scenario_reward_scale,
                sampling_decks_path=str(sampling_decks_path),
                learner_sampling_decks_path=str(learner_sampling_decks_path),
                opponent_sampling_decks_path=str(opponent_sampling_decks_path),
                matchups_path=str(matchups_path) if matchups_path is not None else None,
                matchup_probability=args.matchup_probability,
                trim_rollout_entity_padding=args.trim_rollout_entity_padding,
                hazard_conditioned_rollouts=args.hazard_conditioned_rollouts,
                learner_teacher_strategy=args.online_strategy_teacher,
                learner_teacher_balanced_config=(
                    asdict(learner_teacher_balanced_config)
                    if learner_teacher_balanced_config is not None
                    else None
                ),
            ),
        )
        atexit.register(parallel_collector.close)

    council_opponent_bot = None
    if (
        args.council_opponent_pool is not None
        and parallel_collector is None
        and batched_collector is None
    ):
        from .council_opponents import CouncilLeagueOpponent

        council_opponent_bot = CouncilLeagueOpponent(
            builder=builder,
            learner_model=actor_model,
            pool_path=args.council_opponent_pool,
            seed=rollout_seed,
            assignment_log=Path(args.council_opponent_pool).parent
            / "worker-0-assignments.jsonl",
        )

    agents = (
        args.num_envs
        if args.opponent_mode
        in {
            "noop",
            "random",
            "strategy",
            "checkpoint",
            "league",
        }
        else 2 * args.num_envs
    )
    learner_players = tuple(index % 2 for index in range(args.num_envs))
    recurrent_state = actor_model.initial_state(agents, device=actor_device)
    no_op = model.num_actions - 2
    previous_actions = np.full((agents,), no_op, dtype=np.int64)
    previous_rewards = np.zeros((agents,), dtype=np.float32)
    episode_starts = np.ones((agents,), dtype=np.bool_)
    opponent_previous_actions = np.full((agents,), no_op, dtype=np.int64)
    opponent_previous_rewards = np.zeros((agents,), dtype=np.float32)
    opponent_episode_starts = np.ones((agents,), dtype=np.bool_)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())

    print(f"learner_device={learner_device} actor_device={actor_device}")
    print(f"simulation_backend={args.simulation_backend}")
    print(f"decks_path={decks_path}")
    print(f"sampling_decks_path={sampling_decks_path}")
    print(f"learner_sampling_decks_path={learner_sampling_decks_path}")
    print(f"opponent_sampling_decks_path={opponent_sampling_decks_path}")
    print(
        f"matchups_path={matchups_path} matchup_probability={args.matchup_probability}"
    )
    print(f"checkpoint_dir={directory}")
    print(
        f"model=entity_spatial_recurrent params={parameter_count:,} "
        f"tokens={config.num_tokens} max_entities={config.max_entities} "
        f"d_model={config.d_model} memory={config.memory_size}"
    )
    if anchor_path is not None:
        print(
            f"anchor_checkpoint={anchor_path} anchor_l2_coef={args.anchor_l2_coef} "
            f"anchor_policy_kl_coef={args.anchor_policy_kl_coef} "
            f"anchor_rehearsal_coef={args.anchor_rehearsal_coef}"
        )
    if rehearsal is not None:
        print(
            f"rehearsal_corpus={rehearsal.source} "
            f"rehearsal_chunks={len(rehearsal.chunks)} "
            f"rehearsal_coef={args.rehearsal_coef} "
            f"rehearsal_loss_component={rehearsal.loss_component} "
            f"rehearsal_sequence_length={rehearsal.chunks.shape[1]} "
            f"rehearsal_batch_sequences={args.rehearsal_batch_sequences}"
        )
    if causal_rehearsal is not None:
        print(
            f"causal_rehearsal_corpus={causal_rehearsal.corpus} "
            f"causal_rehearsal_public_sidecar={causal_rehearsal.sidecar} "
            f"causal_rehearsal_chunks={len(causal_rehearsal.chunks)} "
            f"causal_rehearsal_coef={args.causal_rehearsal_coef} "
            "causal_rehearsal_decision_coef="
            f"{args.causal_rehearsal_decision_coef} "
            "causal_rehearsal_decision_positive_weight="
            f"{args.causal_rehearsal_decision_positive_weight} "
            "causal_rehearsal_card_coef="
            f"{args.causal_rehearsal_card_coef} "
            "causal_rehearsal_tile_coef="
            f"{args.causal_rehearsal_tile_coef} "
            "causal_rehearsal_sequence_length="
            f"{causal_rehearsal.chunks.shape[1]} "
            "causal_rehearsal_batch_sequences="
            f"{args.causal_rehearsal_batch_sequences}"
        )
    if causal_spatial_rehearsal is not None:
        print(
            "causal_spatial_rehearsal_corpus="
            f"{causal_spatial_rehearsal.corpus} "
            "causal_spatial_rehearsal_public_sidecar="
            f"{causal_spatial_rehearsal.sidecar} "
            "causal_spatial_rehearsal_chunks="
            f"{len(causal_spatial_rehearsal.chunks)} "
            "causal_spatial_rehearsal_coef="
            f"{args.causal_spatial_rehearsal_coef} "
            "causal_spatial_rehearsal_card_coef="
            f"{args.causal_spatial_rehearsal_card_coef} "
            "causal_spatial_rehearsal_tile_coef="
            f"{args.causal_spatial_rehearsal_tile_coef} "
            "causal_spatial_rehearsal_sequence_length="
            f"{causal_spatial_rehearsal.chunks.shape[1]} "
            "causal_spatial_rehearsal_batch_sequences="
            f"{args.causal_spatial_rehearsal_batch_sequences}"
        )
    if anchor_rehearsal is not None:
        print(
            f"anchor_rehearsal_corpus={anchor_rehearsal.source} "
            f"anchor_rehearsal_chunks={len(anchor_rehearsal.chunks)} "
            f"anchor_rehearsal_coef={args.anchor_rehearsal_coef} "
            "anchor_rehearsal_sequence_length="
            f"{anchor_rehearsal.chunks.shape[1]} "
            "anchor_rehearsal_batch_sequences="
            f"{args.anchor_rehearsal_batch_sequences} "
            "anchor_rehearsal_loss_component="
            f"{anchor_rehearsal.loss_component}"
        )
    print(
        f"envs={args.num_envs} agents={agents} opponent={args.opponent_mode} "
        f"actor_workers={args.actor_workers} "
        f"actor_threads={args.actor_threads} rollout_steps={args.rollout_steps} "
        f"transitions_per_update={agents * args.rollout_steps} "
        f"reward_profile={args.reward_profile} "
        f"reward_shaping_gamma={args.reward_shaping_gamma} "
        f"elixir_leak_penalty_scale={args.elixir_leak_penalty_scale}"
    )
    print(f"hazard_conditioned_rollouts={args.hazard_conditioned_rollouts}")
    entropy_record = entropy_recipe_record(args)
    entropy_name = None
    if getattr(args, "council_config", None) is not None:
        from .council_pilot import entropy_recipe

        entropy_name = entropy_recipe(args)
    print(
        f"entropy_recipe={entropy_name} entropy_coef={args.entropy_coef} "
        f"action_type_entropy_coef={args.action_type_entropy_coef} "
        f"location_entropy_coef={args.location_entropy_coef} "
        f"conditional_slot_entropy_coef={args.conditional_slot_entropy_coef} "
        f"joint_entropy_term_applies={int(entropy_record['joint_entropy_term_applies'])}"
    )
    print(
        f"run_segment={segment_index} rollout_seed={rollout_seed} "
        f"rng_state_restored={int(resume_rng is not None)}"
    )
    if args.opponent_mode == "league":
        league_labels = [
            "random"
            if kind == "random"
            else (f"strategy:{path}" if kind == "strategy" else str(path))
            for kind, path in league_opponents
        ]
        print(f"league_opponents={league_labels}")
    if args.total_decisions is not None:
        planned_rollout_steps(
            total_decisions=total_transitions,
            target_decisions=args.total_decisions,
            checkpoint_decisions=tuple(args.checkpoint_decisions),
            agents=agents,
            rollout_steps=args.rollout_steps,
        )
        args.updates = (
            start_update
            + math.ceil(
                max(0, args.total_decisions - total_transitions)
                / (agents * args.rollout_steps)
            )
            + len(args.checkpoint_decisions)
        )
    if resume_path is not None:
        print(
            f"resumed_from={resume_path} start_update={start_update} "
            f"total_transitions={total_transitions}"
        )
    elif args.preflight_no_update:
        print("preflight_no_update=1 initial_checkpoint=not-written")
        if initial_policy_path is not None:
            print(f"initialized_policy_from={initial_policy_path}")
    else:
        initial_checkpoint = directory / "policy_v2_update_000000.pt"
        save_checkpoint(
            initial_checkpoint,
            model=model,
            optimizer=optimizer,
            builder=builder,
            args=args,
            update=0,
            total_transitions=0,
            simulation_backend_metadata=simulation_backend_metadata,
            council_initialization=council_initialization,
        )
        save_rng_state(
            directory, checkpoint=initial_checkpoint, update=0, rollout_seed=rollout_seed
        )
        print(f"saved_initial_checkpoint={initial_checkpoint}")
        if initial_policy_path is not None:
            print(f"initialized_policy_from={initial_policy_path}")

    if start_update > args.updates:
        print(
            f"nothing_to_do start_update={start_update} target_updates={args.updates}"
        )
        if parallel_collector is not None:
            parallel_collector.close()
            atexit.unregister(parallel_collector.close)
        if batched_collector is not None:
            batched_collector.close()
            atexit.unregister(batched_collector.close)
        return

    training_monitor = None
    if getattr(args, "council_config", None) is not None:
        from .council_monitor import TrainingAlarmMonitor

        # Monitoring only: alarms are logged, never acted on automatically.
        from .council_monitor import initial_opponent_labels

        training_monitor = TrainingAlarmMonitor(
            output_dir=directory,
            token_names=tuple(builder.token_names),
            outcome_dir=(
                Path(args.council_opponent_pool).parent
                if args.council_opponent_pool is not None
                else None
            ),
            card_costs=card_costs_for_monitor(builder),
            opponent_labels=(
                initial_opponent_labels(args.council_opponent_pool)
                if args.council_opponent_pool is not None
                else None
            ),
            resume=resume is not None,
            segment_start_update=start_update,
        )

    def run_ppo_update(
        rollout: RolloutBatch,
        advantages: np.ndarray,
        returns: np.ndarray,
        *,
        critic_only: bool,
        apply_optimizer_step: bool = True,
    ) -> dict[str, float]:
        # One call site for training and the launch preflight, so the
        # preflight exercises the exact PPO/critic-warm-up configuration.
        return ppo_update(
            model=model,
            optimizer=optimizer,
            rollout=rollout,
            advantages=advantages,
            returns=returns,
            device=learner_device,
            epochs=args.epochs,
            sequence_batch_size=args.sequence_batch_size,
            recurrent_update_mode=getattr(args, "recurrent_update_mode", "full-prefix"),
            tbptt_chunk=getattr(args, "tbptt_chunk", 64),
            tbptt_burn_in=getattr(args, "tbptt_burn_in", 16),
            clip_ratio=args.clip_ratio,
            value_coef=args.value_coef,
            action_value_coef=args.action_value_coef,
            entropy_coef=args.entropy_coef,
            action_type_entropy_coef=args.action_type_entropy_coef,
            location_entropy_coef=args.location_entropy_coef,
            conditional_slot_entropy_coef=args.conditional_slot_entropy_coef,
            online_strategy_teacher_coef=args.online_strategy_teacher_coef,
            online_strategy_teacher_decision_coef=(
                args.online_strategy_teacher_decision_coef
            ),
            online_strategy_teacher_card_coef=(
                args.online_strategy_teacher_card_coef
            ),
            online_strategy_teacher_tile_coef=(
                args.online_strategy_teacher_tile_coef
            ),
            online_strategy_teacher_play_weight=(
                args.online_strategy_teacher_play_weight
            ),
            anchor_parameters=anchor_parameters,
            anchor_l2_coef=args.anchor_l2_coef,
            anchor_model=anchor_model,
            anchor_policy_kl_coef=args.anchor_policy_kl_coef,
            rehearsal=rehearsal,
            rehearsal_coef=args.rehearsal_coef,
            rehearsal_batch_sequences=args.rehearsal_batch_sequences,
            causal_rehearsal=causal_rehearsal,
            causal_rehearsal_coef=args.causal_rehearsal_coef,
            causal_rehearsal_decision_coef=(
                args.causal_rehearsal_decision_coef
            ),
            causal_rehearsal_decision_positive_weight=(
                args.causal_rehearsal_decision_positive_weight
            ),
            causal_rehearsal_card_coef=args.causal_rehearsal_card_coef,
            causal_rehearsal_tile_coef=args.causal_rehearsal_tile_coef,
            causal_rehearsal_batch_sequences=(
                args.causal_rehearsal_batch_sequences
            ),
            causal_spatial_rehearsal=causal_spatial_rehearsal,
            causal_spatial_rehearsal_coef=(
                args.causal_spatial_rehearsal_coef
            ),
            causal_spatial_rehearsal_card_coef=(
                args.causal_spatial_rehearsal_card_coef
            ),
            causal_spatial_rehearsal_tile_coef=(
                args.causal_spatial_rehearsal_tile_coef
            ),
            causal_spatial_rehearsal_batch_sequences=(
                args.causal_spatial_rehearsal_batch_sequences
            ),
            anchor_rehearsal=anchor_rehearsal,
            anchor_rehearsal_coef=args.anchor_rehearsal_coef,
            anchor_rehearsal_batch_sequences=(args.anchor_rehearsal_batch_sequences),
            hand_aux_coef=args.hand_aux_coef,
            elixir_aux_coef=args.elixir_aux_coef,
            target_kl=args.target_kl,
            hazard_conditioned_rollouts=args.hazard_conditioned_rollouts,
            sampling_temperature=(
                args.simple_learner_sampling_temperature
            ),
            critic_only=critic_only,
            apply_optimizer_step=apply_optimizer_step,
        )

    preflight: dict[str, Any] | None = None
    if args.preflight_no_update:
        from .council_pilot import state_dict_sha256

        def _forbidden_optimizer_step(*_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("launch preflight must never call optimizer.step()")

        # Belt and braces: ppo_update skips the step in preflight mode, and any
        # stray call on this optimizer instance fails loudly instead.
        optimizer.step = _forbidden_optimizer_step  # type: ignore[method-assign]
        preflight = {
            "schema": "clasher.council-launch-preflight-trainer.v1",
            "gameplay_fitting": False,
            "optimizer_step_calls": 0,
            "checkpoints_written": [],
            "admission": preflight_admission or "not-applicable",
            "seed": args.seed,
            "council_arm": getattr(args, "council_arm", None),
            "critic_warmup_updates": args.critic_warmup_updates,
            "target_kl": args.target_kl,
            "num_envs": args.num_envs,
            "actor_workers": args.actor_workers,
            "configured_rollout_steps": args.rollout_steps,
            "initialization": council_initialization,
            "initialized_policy_path": (
                str(initial_policy_path) if initial_policy_path is not None else None
            ),
            "parameter_count": parameter_count,
            "weights_sha256_before": state_dict_sha256(model.state_dict()),
            "optimizer_state_entries_before": len(optimizer.state),
            "startup_seconds": time.perf_counter() - _MAIN_STARTED,
        }
        if (
            council_initialization is not None
            and preflight["weights_sha256_before"]
            != council_initialization["state_sha256"]
        ):
            raise RuntimeError("preflight weights differ from the initializer digest")

    if preflight is None:
        segment_record = {
            "schema": "clasher.train-run-segment.v1",
            "segment": segment_index,
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "start_update": start_update,
            "target_updates": args.updates,
            "total_transitions_at_start": total_transitions,
            "resumed_from": str(resume_path) if resume_path is not None else None,
            "seed": args.seed,
            "rollout_seed": rollout_seed,
            "rng_state_restored": resume_rng is not None,
            "entropy_recipe": entropy_name,
            "entropy": entropy_record,
            "council_opponent_pool": (
                str(args.council_opponent_pool)
                if args.council_opponent_pool is not None
                else None
            ),
            "council_opponent_pool_sha256": (
                _sha256(args.council_opponent_pool)
                if args.council_opponent_pool is not None
                else None
            ),
        }
        with segments_path.open("a") as stream:
            stream.write(json.dumps(segment_record, sort_keys=True) + "\n")
    if resume is not None:
        if resume_rng is not None:
            restore_rng_state(resume_rng["state"])
        else:
            # No sidecar (older checkpoint) or a repeated resume of this update:
            # use the segment's own seed, never the --seed or an earlier stream.
            import random

            random.seed(rollout_seed)
            np.random.seed(rollout_seed)
            torch.manual_seed(rollout_seed)

    for update in range(start_update, args.updates + 1):
        rollout_steps = planned_rollout_steps(
            total_decisions=total_transitions,
            target_decisions=args.total_decisions,
            checkpoint_decisions=tuple(args.checkpoint_decisions),
            agents=agents,
            rollout_steps=args.rollout_steps,
        )
        if rollout_steps == 0:
            break
        if preflight is not None and args.preflight_rollout_steps is not None:
            rollout_steps = min(rollout_steps, args.preflight_rollout_steps)
        for env in envs:
            env.set_learner_decisions(total_transitions)
        if args.lr_anneal:
            progress = (update - 1) / max(1, args.updates - 1)
            learning_rate = args.learning_rate * max(0.1, 1.0 - progress)
            for group in optimizer.param_groups:
                group["lr"] = learning_rate
        else:
            learning_rate = float(optimizer.param_groups[0]["lr"])

        if council_opponent_bot is not None:
            council_opponent_bot.set_context(
                policy_version=update - 1, learner_decisions=total_transitions
            )
        collect_start = time.perf_counter()
        if simple_collector is not None:
            (
                simple_arrays,
                recurrent_state,
                previous_actions,
                previous_rewards,
                episode_starts,
            ) = simple_collector.collect(rollout_steps, recurrent_state)
            rollout = RolloutBatch(**simple_arrays)
        elif batched_collector is not None:
            rollout = batched_collector.collect(
                model=actor_model,
                rollout_steps=rollout_steps,
                policy_version=update - 1,
                learner_decisions=total_transitions,
                quiet_engine=args.quiet_engine,
                hazard_conditioned_rollouts=args.hazard_conditioned_rollouts,
            )
        elif parallel_collector is None:
            (
                rollout,
                recurrent_state,
                previous_actions,
                previous_rewards,
                episode_starts,
                _,
                opponent_previous_actions,
                opponent_previous_rewards,
                opponent_episode_starts,
            ) = (
                collect_rollout_stationary_opponents(
                    envs=envs,
                    learner_players=learner_players,
                    builder=builder,
                    model=actor_model,
                    device=actor_device,
                    rollout_steps=rollout_steps,
                    recurrent_update_mode=getattr(args, "recurrent_update_mode", "full-prefix"),
                    tbptt_burn_in=getattr(args, "tbptt_burn_in", 16),
                    recurrent_state=recurrent_state,
                    previous_actions=previous_actions,
                    previous_rewards=previous_rewards,
                    episode_starts=episode_starts,
                    opponent_model=None,
                    opponent_recurrent_state=None,
                    opponent_previous_actions=opponent_previous_actions,
                    opponent_previous_rewards=opponent_previous_rewards,
                    opponent_episode_starts=opponent_episode_starts,
                    quiet_engine=args.quiet_engine,
                    hazard_conditioned_rollouts=args.hazard_conditioned_rollouts,
                    opponent_bot=(
                        council_opponent_bot
                        if council_opponent_bot is not None
                        else StrategyBot(args.opponent_strategy)
                        if args.opponent_mode == "strategy"
                        else None
                    ),
                    learner_teacher_bot=learner_teacher_bot,
                    opponent_noop=args.opponent_mode == "noop",
                )
                if args.opponent_mode in {"noop", "random", "strategy"}
                else collect_rollout(
                    envs=envs,
                    builder=builder,
                    model=actor_model,
                    device=actor_device,
                    rollout_steps=rollout_steps,
                    recurrent_update_mode=getattr(args, "recurrent_update_mode", "full-prefix"),
                    tbptt_burn_in=getattr(args, "tbptt_burn_in", 16),
                    recurrent_state=recurrent_state,
                    previous_actions=previous_actions,
                    previous_rewards=previous_rewards,
                    episode_starts=episode_starts,
                    quiet_engine=args.quiet_engine,
                    hazard_conditioned_rollouts=args.hazard_conditioned_rollouts,
                )
                + (
                    None,
                    opponent_previous_actions,
                    opponent_previous_rewards,
                    opponent_episode_starts,
                )
            )
        else:
            rollout = parallel_collector.collect(
                model=model,
                rollout_steps=rollout_steps,
                policy_version=update - 1,
                learner_decisions=total_transitions,
            )
        collect_seconds = time.perf_counter() - collect_start
        if update == start_update and first_rollout_audit_path is not None:
            audit = write_rollout_audit(
                first_rollout_audit_path,
                rollout,
                update=update,
                seed=args.seed,
            )
            print(
                f"first_rollout_audit={first_rollout_audit_path} "
                f"sha256={audit['rollout_sha256']}"
            )
        advantages, returns = compute_gae(
            rollout, gamma=args.gamma, gae_lambda=args.gae_lambda
        )
        if preflight is not None:
            _finish_launch_preflight(
                preflight,
                args=args,
                model=model,
                actor_model=actor_model,
                optimizer=optimizer,
                rollout=rollout,
                advantages=advantages,
                returns=returns,
                run_ppo_update=run_ppo_update,
                scheduled_critic_only=update <= args.critic_warmup_updates,
                collect_seconds=collect_seconds,
                training_monitor=training_monitor,
                update=update,
                directory=directory,
            )
            if parallel_collector is not None:
                parallel_collector.close()
                atexit.unregister(parallel_collector.close)
            if batched_collector is not None:
                batched_collector.close()
                atexit.unregister(batched_collector.close)
            return
        update_start = time.perf_counter()
        stats = run_ppo_update(
            rollout,
            advantages,
            returns,
            critic_only=update <= args.critic_warmup_updates,
        )
        update_seconds = time.perf_counter() - update_start
        sync_start = time.perf_counter()
        if parallel_collector is None:
            synchronize_actor_model(model, actor_model)
        sync_seconds = time.perf_counter() - sync_start
        total_transitions += rollout.transitions

        rejected_actions = (
            int(np.count_nonzero(~rollout.action_success))
            if rollout.action_success is not None
            else 0
        )
        placement = rollout.actions < no_op
        no_op_rate = float(np.mean(rollout.actions == no_op))
        ability_rate = float(np.mean(rollout.actions == no_op + 1))
        non_noop_legal = np.any(rollout.action_masks[..., :no_op], axis=-1)
        non_noop_legal |= rollout.action_masks[..., no_op + 1]
        conditional_no_op = (
            float(np.mean(rollout.actions[non_noop_legal] == no_op))
            if np.any(non_noop_legal)
            else 0.0
        )
        transition_rate = rollout.transitions / max(
            1e-6, collect_seconds + update_seconds + sync_seconds
        )
        if training_monitor is not None:
            try:
                training_monitor.observe_update(
                    update=update,
                    learner_decisions=total_transitions,
                    actions=rollout.actions,
                    hand_ids=rollout.hand_ids,
                    episodes_finished=rollout.episodes_finished,
                    stats=stats,
                    action_masks=rollout.action_masks,
                )
            except Exception as error:  # noqa: BLE001 - monitoring never stops training
                print(f"training_monitor_error={error!r}", flush=True)
        if (
            update % args.log_every == 0
            or update == start_update
            or update == args.updates
        ):
            print(
                f"update={update:05d} transitions={total_transitions} "
                f"reward={float(rollout.rewards.mean()):+.5f} "
                f"abs_reward={float(np.abs(rollout.rewards).mean()):.5f} "
                f"loss={stats['loss']:.4f} policy={stats['policy_loss']:.4f} "
                f"value={stats['value_loss']:.4f} entropy={stats['entropy']:.3f} "
                f"action_q={stats['action_value_loss']:.4f} "
                f"q_gate={stats['action_value_policy_gate']:+.4f} "
                f"type_ent={stats['action_type_entropy']:.3f} "
                f"loc_ent={stats['location_entropy']:.3f} "
                f"card_ent={stats['conditional_slot_entropy']:.3f} "
                f"mode_ent={stats['mode_entropy']:.3f} "
                f"anchor_l2={stats['anchor_l2']:.3f} "
                f"anchor_loss={stats['anchor_loss']:.4f} "
                f"anchor_policy_kl={stats['anchor_policy_kl']:.5f} "
                f"anchor_policy_kl_loss={stats['anchor_policy_kl_loss']:.4f} "
                f"rehearsal={stats['rehearsal_loss']:.3f} "
                f"rehearsal_loss={stats['rehearsal_weighted_loss']:.4f} "
                f"causal_rehearsal={stats['causal_rehearsal_loss']:.3f} "
                "causal_rehearsal_loss="
                f"{stats['causal_rehearsal_weighted_loss']:.4f} "
                "causal_spatial_rehearsal="
                f"{stats['causal_spatial_rehearsal_loss']:.3f} "
                "causal_spatial_rehearsal_loss="
                f"{stats['causal_spatial_rehearsal_weighted_loss']:.4f} "
                f"anchor_rehearsal_kl={stats['anchor_rehearsal_kl']:.5f} "
                f"anchor_rehearsal_loss={stats['anchor_rehearsal_loss']:.4f} "
                f"teacher={stats['online_teacher_loss']:.3f} "
                f"teacher_loss={stats['online_teacher_weighted_loss']:.4f} "
                f"teacher_dct={stats['online_teacher_decision_loss']:.3f}/"
                f"{stats['online_teacher_card_loss']:.3f}/"
                f"{stats['online_teacher_tile_loss']:.3f} "
                f"teacher_acc={stats['online_teacher_decision_accuracy']:.3f}/"
                f"{stats['online_teacher_play_recall']:.3f}/"
                f"{stats['online_teacher_card_accuracy']:.3f}/"
                f"{stats['online_teacher_tile_accuracy']:.3f} "
                f"hand={stats['hand_loss']:.3f} elixir={stats['elixir_loss']:.4f} "
                f"kl={stats['approx_kl']:.5f} clip={stats['clip_fraction']:.3f} "
                f"opt_steps={int(stats['optimizer_steps'])} "
                f"kl_stop={int(stats['kl_early_stop'])} "
                f"critic_warmup={int(stats['critic_warmup'])} "
                f"ev={stats['explained_variance']:+.3f} "
                f"play={float(placement.mean()):.3f} noop={no_op_rate:.3f} "
                f"noop_when_playable={conditional_no_op:.3f} "
                f"ability={ability_rate:.4f} episodes={rollout.episodes_finished} "
                f"rejected_actions={rejected_actions} "
                f"wld={rollout.wins}/{rollout.losses}/{rollout.draws} "
                f"collect_s={collect_seconds:.2f} learn_s={update_seconds:.2f} "
                f"sync_s={sync_seconds:.2f} "
                f"tps={transition_rate:.1f} lr={learning_rate:.2e}"
            )

        if (
            update % args.save_every == 0
            or update == args.updates
            or total_transitions in args.checkpoint_decisions
            or total_transitions == args.total_decisions
        ):
            checkpoint = directory / f"policy_v2_update_{update:06d}.pt"
            save_checkpoint(
                checkpoint,
                model=model,
                optimizer=optimizer,
                builder=builder,
                args=args,
                update=update,
                total_transitions=total_transitions,
                simulation_backend_metadata=simulation_backend_metadata,
                council_initialization=council_initialization,
                metrics={
                    **stats,
                    "reward_mean": float(rollout.rewards.mean()),
                    "absolute_reward_mean": float(np.abs(rollout.rewards).mean()),
                    "play_rate": float(placement.mean()),
                    "noop_rate": no_op_rate,
                    "noop_when_playable": conditional_no_op,
                    "ability_rate": ability_rate,
                    "collect_seconds": collect_seconds,
                    "learn_seconds": update_seconds,
                    "sync_seconds": sync_seconds,
                    "transitions_per_second": transition_rate,
                },
            )
            save_rng_state(
                directory, checkpoint=checkpoint, update=update, rollout_seed=rollout_seed
            )
            print(f"saved_checkpoint={checkpoint}")
            if training_monitor is not None:
                try:
                    training_monitor.observe_checkpoint(
                        update=update,
                        learner_decisions=total_transitions,
                        checkpoint=str(checkpoint),
                    )
                except Exception as error:  # noqa: BLE001 - monitoring only
                    print(f"training_monitor_error={error!r}", flush=True)
            if (
                args.council_opponent_pool is not None
                and total_transitions >= 1_000_000
            ):
                from .council_pilot import retain_league_checkpoint

                retain_league_checkpoint(
                    args.council_opponent_pool, checkpoint, total_transitions
                )

            if (
                total_transitions in args.checkpoint_decisions
                or total_transitions == args.total_decisions
            ):
                import shutil

                milestone = directory / f"policy_decisions_{total_transitions:09d}.pt"
                temporary_milestone = milestone.with_suffix(".tmp")
                shutil.copyfile(checkpoint, temporary_milestone)
                os.replace(temporary_milestone, milestone)
                print(f"saved_decision_checkpoint={milestone}")

    if parallel_collector is not None:
        parallel_collector.close()
        atexit.unregister(parallel_collector.close)
    if batched_collector is not None:
        batched_collector.close()
        atexit.unregister(batched_collector.close)


if __name__ == "__main__":
    main()
