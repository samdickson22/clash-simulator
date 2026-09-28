"""Exact input reuse for DAgger behavior policies and stationary opponents."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from .model import ClasherPolicy, PolicyInputs
from .selfplay_env import SelfPlayBattleEnv
from .strategy_bots import STRATEGY_NAMES, StrategyBot
from .structured_obs import ActorObservation, StructuredObservationBuilder

RANDOM_OPPONENT = "random"
STRATEGY_PREFIX = "strategy:"


@dataclass(frozen=True)
class PreparedBehaviorDecision:
    """Inputs computed once and shared by labeling, acting, and environment step."""

    observations: dict[int, ActorObservation]
    action_masks: dict[int, np.ndarray]


def prepare_behavior_decision(
    env: SelfPlayBattleEnv,
    builder: StructuredObservationBuilder,
    *,
    observation_players: tuple[int, ...],
) -> PreparedBehaviorDecision:
    """Build both legal masks once and public observations only where requested."""
    if env.battle is None:
        raise ValueError("environment must be reset before preparing a decision")
    if len(set(observation_players)) != len(observation_players):
        raise ValueError("observation_players must not contain duplicates")
    if any(player_id not in (0, 1) for player_id in observation_players):
        raise ValueError("observation_players must contain only players 0 and 1")

    requested = set(observation_players)
    observations: dict[int, ActorObservation] = {}
    action_masks: dict[int, np.ndarray] = {}
    for player_id in (0, 1):
        if player_id in requested:
            observations[player_id] = builder.build_actor(env.battle, player_id)
        action_masks[player_id] = env.get_action_mask(player_id)
    return PreparedBehaviorDecision(
        observations=observations,
        action_masks=action_masks,
    )


def _actor_step_inputs(
    observation: ActorObservation,
    action_mask: np.ndarray,
    *,
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
    device: torch.device,
) -> PolicyInputs:
    def tensor(value: np.ndarray, dtype: torch.dtype) -> torch.Tensor:
        return torch.as_tensor(value, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)

    return PolicyInputs(
        entity_ids=tensor(observation.entity_ids, torch.long),
        entity_features=tensor(observation.entity_features, torch.float32),
        entity_mask=tensor(observation.entity_mask, torch.bool),
        hand_ids=tensor(observation.hand_ids, torch.long),
        global_features=tensor(observation.global_features, torch.float32),
        action_mask=tensor(np.asarray(action_mask, dtype=np.bool_), torch.bool),
        previous_actions=torch.as_tensor(
            [[previous_action]], dtype=torch.long, device=device
        ),
        previous_rewards=torch.as_tensor(
            [[previous_reward]], dtype=torch.float32, device=device
        ),
        episode_starts=torch.as_tensor(
            [[episode_start]], dtype=torch.bool, device=device
        ),
    )


@torch.no_grad()
def actor_policy_action(
    model: ClasherPolicy,
    observation: ActorObservation,
    action_mask: np.ndarray,
    *,
    state: tuple[torch.Tensor, torch.Tensor],
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
    deterministic: bool,
    device: torch.device,
) -> tuple[int, tuple[torch.Tensor, torch.Tensor]]:
    """Act from prebuilt public inputs without evaluating the critic encoder."""
    inputs = _actor_step_inputs(
        observation,
        action_mask,
        previous_action=previous_action,
        previous_reward=previous_reward,
        episode_start=episode_start,
        device=device,
    )
    if model.config.public_observation_confidence:
        inputs = inputs.with_exact_actor_confidence()
    action, _, _, next_state, _ = model.act(
        inputs,
        state,
        deterministic=deterministic,
    )
    return int(action[0, 0].item()), next_state


def parse_stationary_opponent(spec: str) -> StrategyBot | None:
    """Resolve ``random`` or a data-driven ``strategy:<name>`` opponent."""
    if spec == RANDOM_OPPONENT:
        return None
    if spec.startswith(STRATEGY_PREFIX):
        name = spec.removeprefix(STRATEGY_PREFIX)
        if name in STRATEGY_NAMES:
            return StrategyBot(name)
    choices = ", ".join([RANDOM_OPPONENT, *(f"{STRATEGY_PREFIX}{n}" for n in STRATEGY_NAMES)])
    raise ValueError(f"unknown stationary opponent {spec!r}; expected one of: {choices}")


def stationary_action(
    env: SelfPlayBattleEnv,
    player_id: int,
    action_mask: np.ndarray,
    *,
    rng: np.random.Generator,
    strategy_bot: StrategyBot | None,
) -> int:
    """Select a legal stationary action while reusing the caller's mask."""
    if strategy_bot is not None:
        return strategy_bot.select_action(
            env,
            player_id,
            action_mask=action_mask,
        )
    legal = np.flatnonzero(np.asarray(action_mask, dtype=np.bool_))
    if legal.size == 0:
        return env.action_space.no_op_action
    return int(rng.choice(legal))


def behavior_player_for_episode(shard_index: int, episode_id: int) -> int:
    """Balance behavior seats deterministically across shards and episodes."""
    if shard_index < 0 or episode_id < 0:
        raise ValueError("shard_index and episode_id must be non-negative")
    return (shard_index + episode_id) % 2
