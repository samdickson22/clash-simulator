from __future__ import annotations

import argparse
import atexit
import time
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

from .model import ClasherPolicy, PolicyConfig, PolicyInputs
from .selfplay_env import SelfPlayBattleEnv
from .structured_obs import StructuredObservation, StructuredObservationBuilder


class _NullWriter:
    def write(self, _value: Any) -> int:
        return 0

    def flush(self) -> None:
        return None


_NULL_WRITER = _NullWriter()


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

    @property
    def num_sequences(self) -> int:
        return int(self.actions.shape[0])

    @property
    def sequence_length(self) -> int:
        return int(self.actions.shape[1])

    @property
    def transitions(self) -> int:
        return int(self.actions.size)


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


def _stack_step_inputs(
    observations: list[StructuredObservation],
    action_masks: np.ndarray,
    previous_actions: np.ndarray,
    previous_rewards: np.ndarray,
    episode_starts: np.ndarray,
    device: torch.device,
) -> PolicyInputs:
    def stack(name: str, dtype: torch.dtype) -> Tensor:
        array = np.stack([getattr(observation, name) for observation in observations])
        return torch.as_tensor(array, dtype=dtype, device=device).unsqueeze(1)

    return PolicyInputs(
        entity_ids=stack("entity_ids", torch.long),
        entity_features=stack("entity_features", torch.float32),
        entity_mask=stack("entity_mask", torch.bool),
        hand_ids=stack("hand_ids", torch.long),
        global_features=stack("global_features", torch.float32),
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


def _empty_rollout_arrays(
    *,
    agents: int,
    steps: int,
    builder: StructuredObservationBuilder,
    num_actions: int,
) -> dict[str, np.ndarray]:
    spec = builder.spec
    return {
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
    }


def _store_observations(
    arrays: dict[str, np.ndarray],
    observations: list[StructuredObservation],
    action_masks: np.ndarray,
    previous_actions: np.ndarray,
    previous_rewards: np.ndarray,
    episode_starts: np.ndarray,
    step: int,
) -> None:
    observation_fields = (
        "entity_ids",
        "entity_features",
        "entity_mask",
        "hand_ids",
        "global_features",
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
    arrays["action_masks"][:, step] = action_masks
    arrays["previous_actions"][:, step] = previous_actions
    arrays["previous_rewards"][:, step] = previous_rewards
    arrays["episode_starts"][:, step] = episode_starts


def _current_observations(
    envs: list[SelfPlayBattleEnv],
) -> tuple[list[StructuredObservation], np.ndarray]:
    observations: list[StructuredObservation] = []
    masks: list[np.ndarray] = []
    for env in envs:
        for player_id in (0, 1):
            observations.append(env.get_structured_observation(player_id))
            masks.append(env.get_action_mask(player_id))
    return observations, np.stack(masks)


def _current_learner_observations(
    envs: list[SelfPlayBattleEnv],
    learner_players: tuple[int, ...],
) -> tuple[list[StructuredObservation], np.ndarray]:
    if len(envs) != len(learner_players):
        raise ValueError("learner_players must have one seat per environment")
    observations: list[StructuredObservation] = []
    masks: list[np.ndarray] = []
    for env, player_id in zip(envs, learner_players):
        observations.append(env.get_structured_observation(player_id))
        masks.append(env.get_action_mask(player_id))
    return observations, np.stack(masks)


def _current_action_masks(
    envs: list[SelfPlayBattleEnv],
    players: tuple[int, ...],
) -> np.ndarray:
    if len(envs) != len(players):
        raise ValueError("players must have one seat per environment")
    return np.stack(
        [
            env.get_action_mask(player_id)
            for env, player_id in zip(envs, players)
        ]
    )


@torch.no_grad()
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
) -> tuple[RolloutBatch, tuple[Tensor, Tensor], np.ndarray, np.ndarray, np.ndarray]:
    model.eval()
    agents = len(envs) * 2
    num_actions = envs[0].action_space.num_actions
    arrays = _empty_rollout_arrays(
        agents=agents,
        steps=rollout_steps,
        builder=builder,
        num_actions=num_actions,
    )
    initial_hidden = recurrent_state[0].detach().cpu().numpy().copy()
    initial_cell = recurrent_state[1].detach().cpu().numpy().copy()
    episodes_finished = 0
    wins = losses = draws = 0

    for step in range(rollout_steps):
        with maybe_silence_stdio(quiet_engine):
            observations, action_masks = _current_observations(envs)
        _store_observations(
            arrays,
            observations,
            action_masks,
            previous_actions,
            previous_rewards,
            episode_starts,
            step,
        )
        inputs = _stack_step_inputs(
            observations,
            action_masks,
            previous_actions,
            previous_rewards,
            episode_starts,
            device,
        )
        actions_t, log_probs_t, values_t, recurrent_state, _ = model.act(
            inputs, recurrent_state, deterministic=False
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
                rewards, done, _ = env.step(
                    {0: int(actions[base]), 1: int(actions[base + 1])},
                    pre_action_masks={
                        0: action_masks[base],
                        1: action_masks[base + 1],
                    },
                )
                arrays["rewards"][base, step] = float(rewards[0])
                arrays["rewards"][base + 1, step] = float(rewards[1])
                arrays["dones"][base : base + 2, step] = done
                next_previous_rewards[base] = float(rewards[0])
                next_previous_rewards[base + 1] = float(rewards[1])
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
        bootstrap_observations, bootstrap_masks = _current_observations(envs)
    bootstrap_inputs = _stack_step_inputs(
        bootstrap_observations,
        bootstrap_masks,
        previous_actions,
        previous_rewards,
        episode_starts,
        device,
    )
    bootstrap_values = model.forward(bootstrap_inputs, recurrent_state).values[:, 0]

    rollout = RolloutBatch(
        **arrays,
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


@torch.no_grad()
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
    """Collect one learner seat against a random or frozen recurrent policy.

    Seats alternate across environments, and only learner-controlled decisions
    enter the rollout. This gives PPO a stationary anchor without contaminating
    the loss with actions sampled by the opponent policy.
    """

    model.eval()
    if opponent_model is not None:
        opponent_model.eval()
        if opponent_recurrent_state is None:
            raise ValueError("checkpoint opponent requires recurrent state")
    agents = len(envs)
    if agents != len(learner_players):
        raise ValueError("learner_players must have one seat per environment")
    num_actions = envs[0].action_space.num_actions
    arrays = _empty_rollout_arrays(
        agents=agents,
        steps=rollout_steps,
        builder=builder,
        num_actions=num_actions,
    )
    initial_hidden = recurrent_state[0].detach().cpu().numpy().copy()
    initial_cell = recurrent_state[1].detach().cpu().numpy().copy()
    episodes_finished = wins = losses = draws = 0

    for step in range(rollout_steps):
        with maybe_silence_stdio(quiet_engine):
            observations, action_masks = _current_learner_observations(
                envs, learner_players
            )
        _store_observations(
            arrays,
            observations,
            action_masks,
            previous_actions,
            previous_rewards,
            episode_starts,
            step,
        )
        inputs = _stack_step_inputs(
            observations,
            action_masks,
            previous_actions,
            previous_rewards,
            episode_starts,
            device,
        )
        actions_t, log_probs_t, values_t, recurrent_state, _ = model.act(
            inputs, recurrent_state, deterministic=False
        )
        actions = actions_t[:, 0].cpu().numpy().astype(np.int64, copy=False)
        arrays["actions"][:, step] = actions
        arrays["old_log_probs"][:, step] = log_probs_t[:, 0].cpu().numpy()
        arrays["old_values"][:, step] = values_t[:, 0].cpu().numpy()

        opponent_players = tuple(1 - player_id for player_id in learner_players)
        with maybe_silence_stdio(quiet_engine):
            if opponent_model is None:
                # Random opponents consume only legal masks. Avoid building
                # their unused public and privileged observation tables.
                opponent_observations = None
                opponent_masks = _current_action_masks(envs, opponent_players)
            else:
                opponent_observations, opponent_masks = (
                    _current_learner_observations(envs, opponent_players)
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
                rewards, done, _ = env.step(
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
                next_previous_rewards[env_index] = learner_reward
                next_opponent_previous_rewards[env_index] = float(
                    rewards[opponent_player]
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
            envs, learner_players
        )
    bootstrap_inputs = _stack_step_inputs(
        bootstrap_observations,
        bootstrap_masks,
        previous_actions,
        previous_rewards,
        episode_starts,
        device,
    )
    bootstrap_values = model.forward(bootstrap_inputs, recurrent_state).values[:, 0]
    rollout = RolloutBatch(
        **arrays,
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
        entity_ids=tensor("entity_ids", torch.long),
        entity_features=tensor("entity_features", torch.float32),
        entity_mask=tensor("entity_mask", torch.bool),
        hand_ids=tensor("hand_ids", torch.long),
        global_features=tensor("global_features", torch.float32),
        action_mask=tensor("action_masks", torch.bool),
        previous_actions=tensor("previous_actions", torch.long),
        previous_rewards=tensor("previous_rewards", torch.float32),
        episode_starts=tensor("episode_starts", torch.bool),
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
        entity_ids=inputs.entity_ids.index_select(0, indices),
        entity_features=inputs.entity_features.index_select(0, indices),
        entity_mask=inputs.entity_mask.index_select(0, indices),
        hand_ids=inputs.hand_ids.index_select(0, indices),
        global_features=inputs.global_features.index_select(0, indices),
        action_mask=inputs.action_mask.index_select(0, indices),
        previous_actions=inputs.previous_actions.index_select(0, indices),
        previous_rewards=inputs.previous_rewards.index_select(0, indices),
        episode_starts=inputs.episode_starts.index_select(0, indices),
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
) -> dict[str, float]:
    model.train()
    normalized_advantages = (advantages - float(advantages.mean())) / (
        float(advantages.std()) + 1e-8
    )
    stat_sums = {
        "loss": 0.0,
        "policy_loss": 0.0,
        "value_loss": 0.0,
        "entropy": 0.0,
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

    for _epoch in range(epochs):
        order = np.random.permutation(rollout.num_sequences)
        for start in range(0, rollout.num_sequences, sequence_batch_size):
            indices = order[start : start + sequence_batch_size]
            index_tensor = torch.as_tensor(indices, dtype=torch.long, device=device)
            inputs = _index_policy_inputs(all_inputs, index_tensor)
            initial_state = (
                all_initial_hidden.index_select(0, index_tensor),
                all_initial_cell.index_select(0, index_tensor),
            )
            output = model(inputs, initial_state)
            distribution = output.distribution()
            actions = all_actions.index_select(0, index_tensor)
            old_log_prob = all_old_log_prob.index_select(0, index_tensor)
            old_values = all_old_values.index_select(0, index_tensor)
            advantage = all_advantages.index_select(0, index_tensor)
            return_target = all_returns.index_select(0, index_tensor)

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
            entropy = distribution.entropy().mean()

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
            loss = (
                policy_loss
                + value_coef * value_loss
                - entropy_coef * entropy
                + hand_aux_coef * hand_loss
                + elixir_aux_coef * elixir_loss
            )

            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            grad_norm = nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            optimizer.step()

            with torch.no_grad():
                approx_kl = ((ratio - 1.0) - log_ratio).mean()
                clip_fraction = ((ratio - 1.0).abs() > clip_ratio).float().mean()
            values = {
                "loss": loss,
                "policy_loss": policy_loss,
                "value_loss": value_loss,
                "entropy": entropy,
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

    if updates:
        for key in stat_sums:
            stat_sums[key] /= updates
    stat_sums["optimizer_steps"] = float(updates)
    stat_sums["kl_early_stop"] = float(stop_early)
    prediction = rollout.old_values.reshape(-1)
    target = returns.reshape(-1)
    variance = float(np.var(target))
    stat_sums["explained_variance"] = (
        float(1.0 - np.var(target - prediction) / variance) if variance > 1e-8 else 0.0
    )
    return stat_sums


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
) -> None:
    torch.save(
        {
            "format_version": 2,
            "model_type": "entity_spatial_recurrent",
            "model_config": model.config.to_dict(),
            "token_names": builder.token_names,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "args": vars(args),
            "update": update,
            "total_transitions": total_transitions,
            "metrics": metrics or {},
        },
        path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the recurrent entity-spatial policy with PPO self-play"
    )
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--checkpoint-dir", default="checkpoints/entity_selfplay")
    parser.add_argument("--resume-latest", action="store_true")
    parser.add_argument("--resume-from", default=None)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--updates", type=int, default=500)
    parser.add_argument("--num-envs", type=int, default=6)
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
    parser.add_argument("--rollout-steps", type=int, default=48)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument("--mirror-match", action="store_true")
    parser.add_argument(
        "--opponent-mode",
        choices=["selfplay", "random", "checkpoint", "league"],
        default="selfplay",
        help=(
            "selfplay trains both seats with the current policy; random trains "
            "one balanced learner seat per environment against a stationary "
            "uniform-legal opponent; checkpoint uses frozen policies; league "
            "mixes repeated random/checkpoint specifications across workers"
        ),
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
        metavar="RANDOM_OR_CHECKPOINT",
        help=(
            "repeat in league mode; each value is 'random' or a frozen V2 "
            "checkpoint path, distributed round-robin across workers"
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
    parser.add_argument("--d-model", type=int, default=128)
    parser.add_argument("--num-heads", type=int, default=4)
    parser.add_argument("--actor-layers", type=int, default=4)
    parser.add_argument("--critic-layers", type=int, default=2)
    parser.add_argument("--memory-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=2.5e-4)
    parser.add_argument("--gamma", type=float, default=0.995)
    parser.add_argument("--gae-lambda", type=float, default=0.95)
    parser.add_argument("--clip-ratio", type=float, default=0.2)
    parser.add_argument("--value-coef", type=float, default=0.5)
    parser.add_argument("--entropy-coef", type=float, default=0.01)
    parser.add_argument("--hand-aux-coef", type=float, default=0.02)
    parser.add_argument("--elixir-aux-coef", type=float, default=0.05)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--sequence-batch-size", type=int, default=2)
    parser.add_argument("--target-kl", type=float, default=0.03)
    parser.add_argument("--save-every", type=int, default=10)
    parser.add_argument("--log-every", type=int, default=1)
    parser.add_argument("--no-lr-anneal", dest="lr_anneal", action="store_false")
    parser.add_argument(
        "--quiet-engine", dest="quiet_engine", action="store_true", default=True
    )
    parser.add_argument("--no-quiet-engine", dest="quiet_engine", action="store_false")
    return parser.parse_args()


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


def main() -> None:
    args = parse_args()
    if args.num_envs <= 0 or args.rollout_steps <= 0:
        raise ValueError("num_envs and rollout_steps must be positive")
    if args.actor_workers <= 0 or args.actor_workers > args.num_envs:
        raise ValueError("actor_workers must be between 1 and num_envs")
    if args.actor_threads <= 0:
        raise ValueError("actor_threads must be positive")
    if args.opponent_mode == "checkpoint" and not args.opponent_checkpoint:
        raise ValueError("--opponent-mode checkpoint requires --opponent-checkpoint")
    if args.opponent_mode != "checkpoint" and args.opponent_checkpoint:
        raise ValueError("--opponent-checkpoint requires --opponent-mode checkpoint")
    if args.opponent_mode == "league" and not args.league_opponent:
        raise ValueError("--opponent-mode league requires --league-opponent")
    if args.opponent_mode != "league" and args.league_opponent:
        raise ValueError("--league-opponent requires --opponent-mode league")
    if args.opponent_mode in {"checkpoint", "league"} and args.actor_workers == 1:
        raise ValueError(
            "checkpoint and league opponents currently require parallel actors"
        )
    if args.opponent_mode == "league":
        league_kinds = {
            "random" if spec == "random" else "checkpoint"
            for spec in args.league_opponent
        }
        if league_kinds != {"random", "checkpoint"}:
            raise ValueError(
                "league mode requires at least one random and one checkpoint opponent"
            )
    if args.d_model % args.num_heads != 0:
        raise ValueError("d_model must be divisible by num_heads")

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    torch.set_num_threads(max(1, min(8, torch.get_num_threads())))
    learner_device = resolve_learner_device(args.device)
    actor_device = resolve_torch_device(args.actor_device)
    if args.actor_workers > 1 and actor_device.type != "cpu":
        raise ValueError(
            "parallel rollout workers currently require --actor-device cpu"
        )
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    opponent_checkpoints = tuple(
        str(resolve_path(path, must_exist=True)) for path in args.opponent_checkpoint
    )
    league_opponents = tuple(
        ("random", None)
        if spec == "random"
        else ("checkpoint", str(resolve_path(spec, must_exist=True)))
        for spec in args.league_opponent
    )
    directory = checkpoints_dir(args.checkpoint_dir, create=True)
    resume, resume_path = _load_resume_state(args, directory, learner_device)

    token_names = resume.get("token_names") if resume is not None else None
    resume_config = (
        PolicyConfig.from_dict(resume["model_config"]) if resume is not None else None
    )
    builder = StructuredObservationBuilder(
        decks_path=decks_path,
        max_entities=(resume_config.max_entities if resume_config else 128),
        token_names=token_names,
    )
    config = resume_config or PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.spec.max_entities,
        d_model=args.d_model,
        num_heads=args.num_heads,
        actor_layers=args.actor_layers,
        critic_layers=args.critic_layers,
        memory_size=args.memory_size,
    )
    model = ClasherPolicy(config, builder.card_stat_features).to(learner_device)
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
        model.load_state_dict(resume["model_state_dict"])
        if "optimizer_state_dict" in resume:
            restore_optimizer_state(
                optimizer,
                resume["optimizer_state_dict"],
                learning_rate=args.learning_rate,
            )
        start_update = int(resume.get("update", 0)) + 1
        total_transitions = int(resume.get("total_transitions", 0))
    synchronize_actor_model(model, actor_model)

    envs: list[SelfPlayBattleEnv] = []
    parallel_collector: Any = None
    if args.actor_workers == 1:
        with maybe_silence_stdio(args.quiet_engine):
            for index in range(args.num_envs):
                env = SelfPlayBattleEnv(
                    decision_interval_ticks=args.decision_interval,
                    max_ticks=args.max_ticks,
                    decks_path=decks_path,
                    seed=args.seed + index * 1009,
                    mirror_match=args.mirror_match,
                    canonical_perspective=True,
                    engine_fast_path=args.engine_fast_path,
                )
                env._structured_obs_builder = builder
                env.reset(seed=args.seed + index * 1009)
                envs.append(env)
    else:
        from .parallel_rollout import (
            ActorWorkerConfig,
            OpponentSpec,
            ParallelRolloutCollector,
        )

        opponent_pool: tuple[OpponentSpec, ...]
        if args.opponent_mode == "random":
            opponent_pool = (OpponentSpec(kind="random"),)
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
                    else OpponentSpec(kind="checkpoint", checkpoint=path)
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
                decision_interval=args.decision_interval,
                max_ticks=args.max_ticks,
                mirror_match=args.mirror_match,
                opponent_mode=args.opponent_mode,
                opponent_pool=opponent_pool,
                engine_fast_path=args.engine_fast_path,
                quiet_engine=args.quiet_engine,
                base_seed=args.seed,
                torch_threads=args.actor_threads,
            ),
        )
        atexit.register(parallel_collector.close)

    agents = (
        args.num_envs
        if args.opponent_mode in {"random", "checkpoint", "league"}
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
    print(f"decks_path={decks_path}")
    print(f"checkpoint_dir={directory}")
    print(
        f"model=entity_spatial_recurrent params={parameter_count:,} "
        f"tokens={config.num_tokens} max_entities={config.max_entities} "
        f"d_model={config.d_model} memory={config.memory_size}"
    )
    print(
        f"envs={args.num_envs} agents={agents} opponent={args.opponent_mode} "
        f"actor_workers={args.actor_workers} "
        f"actor_threads={args.actor_threads} rollout_steps={args.rollout_steps} "
        f"transitions_per_update={agents * args.rollout_steps}"
    )
    if args.opponent_mode == "league":
        league_labels = [
            "random" if kind == "random" else str(path)
            for kind, path in league_opponents
        ]
        print(f"league_opponents={league_labels}")
    if resume_path is not None:
        print(
            f"resumed_from={resume_path} start_update={start_update} "
            f"total_transitions={total_transitions}"
        )
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
        )
        print(f"saved_initial_checkpoint={initial_checkpoint}")

    if start_update > args.updates:
        print(
            f"nothing_to_do start_update={start_update} target_updates={args.updates}"
        )
        if parallel_collector is not None:
            parallel_collector.close()
            atexit.unregister(parallel_collector.close)
        return

    for update in range(start_update, args.updates + 1):
        if args.lr_anneal:
            progress = (update - 1) / max(1, args.updates - 1)
            learning_rate = args.learning_rate * max(0.1, 1.0 - progress)
            for group in optimizer.param_groups:
                group["lr"] = learning_rate
        else:
            learning_rate = float(optimizer.param_groups[0]["lr"])

        collect_start = time.perf_counter()
        if parallel_collector is None:
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
                    rollout_steps=args.rollout_steps,
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
                )
                if args.opponent_mode == "random"
                else collect_rollout(
                    envs=envs,
                    builder=builder,
                    model=actor_model,
                    device=actor_device,
                    rollout_steps=args.rollout_steps,
                    recurrent_state=recurrent_state,
                    previous_actions=previous_actions,
                    previous_rewards=previous_rewards,
                    episode_starts=episode_starts,
                    quiet_engine=args.quiet_engine,
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
                rollout_steps=args.rollout_steps,
                policy_version=update - 1,
            )
        collect_seconds = time.perf_counter() - collect_start
        advantages, returns = compute_gae(
            rollout, gamma=args.gamma, gae_lambda=args.gae_lambda
        )
        update_start = time.perf_counter()
        stats = ppo_update(
            model=model,
            optimizer=optimizer,
            rollout=rollout,
            advantages=advantages,
            returns=returns,
            device=learner_device,
            epochs=args.epochs,
            sequence_batch_size=args.sequence_batch_size,
            clip_ratio=args.clip_ratio,
            value_coef=args.value_coef,
            entropy_coef=args.entropy_coef,
            hand_aux_coef=args.hand_aux_coef,
            elixir_aux_coef=args.elixir_aux_coef,
            target_kl=args.target_kl,
        )
        update_seconds = time.perf_counter() - update_start
        sync_start = time.perf_counter()
        if parallel_collector is None:
            synchronize_actor_model(model, actor_model)
        sync_seconds = time.perf_counter() - sync_start
        total_transitions += rollout.transitions

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
                f"hand={stats['hand_loss']:.3f} elixir={stats['elixir_loss']:.4f} "
                f"kl={stats['approx_kl']:.5f} clip={stats['clip_fraction']:.3f} "
                f"opt_steps={int(stats['optimizer_steps'])} "
                f"kl_stop={int(stats['kl_early_stop'])} "
                f"ev={stats['explained_variance']:+.3f} "
                f"play={float(placement.mean()):.3f} noop={no_op_rate:.3f} "
                f"noop_when_playable={conditional_no_op:.3f} "
                f"ability={ability_rate:.4f} episodes={rollout.episodes_finished} "
                f"wld={rollout.wins}/{rollout.losses}/{rollout.draws} "
                f"collect_s={collect_seconds:.2f} learn_s={update_seconds:.2f} "
                f"sync_s={sync_seconds:.2f} "
                f"tps={transition_rate:.1f} lr={learning_rate:.2e}"
            )

        if update % args.save_every == 0 or update == args.updates:
            checkpoint = directory / f"policy_v2_update_{update:06d}.pt"
            save_checkpoint(
                checkpoint,
                model=model,
                optimizer=optimizer,
                builder=builder,
                args=args,
                update=update,
                total_transitions=total_transitions,
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
            print(f"saved_checkpoint={checkpoint}")

    if parallel_collector is not None:
        parallel_collector.close()
        atexit.unregister(parallel_collector.close)


if __name__ == "__main__":
    main()
