"""Train public belief on exact delayed tactical counterfactual card choices."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.deck_pool import load_deck_pool
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.model import ClasherPolicy, PolicyInputs, PolicyOutput
from clasher.rl.reward_model import (
    DEFENSE_V2,
    potential_breakdown_p0,
    reward_potential_p0,
)
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import (
    BALANCED,
    REACTIVE_DEFENSE,
    SLOW_PUSH,
    StrategyBot,
)
from clasher.rl.structured_obs import ActorObservation, StructuredObservationBuilder

RELATIONAL_TRAINABLE_NAMES = (
    "public_belief_card_query.weight",
    "public_belief_timing_head.weight",
)
COUNTERFACTUAL_VALUE_PROFILE = "defense-v2-resource-balanced-v1"
COUNTERFACTUAL_CONTINUATION = "frozen-policy-and-same-strategy-v1"


def counterfactual_win_prob_p0(battle: BattleState) -> float:
    """Score delayed outcomes without rewarding elixir-to-board conversion.

    Defense-v2's board term is appropriate for temporal-difference rewards,
    where the elixir spend was observed on the transition. A root-action
    counterfactual compares deployed cards against no-op directly: crediting a
    new troop's material without debiting its elixir makes every deployment
    look like free value. Pair the public board value with the remaining-elixir
    edge on the same 16-elixir normalization used by the board-value term.
    """
    if battle.game_over:
        if battle.winner is None:
            return 0.5
        return 1.0 if battle.winner == 0 else 0.0
    breakdown = potential_breakdown_p0(battle)
    elixir_edge = (
        float(battle.players[0].elixir) - float(battle.players[1].elixir)
    ) / 16.0
    resource_board = breakdown.board_value + elixir_edge
    potential = (
        breakdown.objective_v1
        + 0.08 * resource_board
        + 0.12 * breakdown.tower_danger
    )
    return float(1.0 / (1.0 + np.exp(-2.5 * np.clip(potential, -1.5, 1.5))))


@dataclass(frozen=True)
class TacticalSample:
    observation: ActorObservation
    action_mask: np.ndarray
    previous_action: int
    previous_reward: float
    episode_start: bool
    hidden: np.ndarray
    cell: np.ndarray
    target_type: int
    base_type: int
    incoming_danger: float
    candidate_scores: np.ndarray
    score_margin: float
    episode_id: int
    battle_tick: int
    learner_player: int
    learner_deck_key: str
    opponent_deck_key: str


def action_type(action: int, action_space: DiscreteTileActionSpace) -> int:
    if action < NUM_HAND_SLOTS * NUM_TILES:
        return action // NUM_TILES
    if action == action_space.no_op_action:
        return NUM_HAND_SLOTS
    if action == action_space.ability_action:
        return NUM_HAND_SLOTS + 1
    raise ValueError(f"action {action} is outside the discrete action space")


def candidate_actions_from_output(
    output: PolicyOutput,
    action_mask: np.ndarray,
    action_space: DiscreteTileActionSpace,
) -> dict[int, int]:
    """Choose one frozen-policy placement per legal action type."""
    mask = np.asarray(action_mask, dtype=np.bool_)
    if mask.shape != (action_space.num_actions,):
        raise ValueError("counterfactual action mask has the wrong shape")
    candidates: dict[int, int] = {}
    placement_mask = mask[: action_space.no_op_action].reshape(
        NUM_HAND_SLOTS,
        NUM_TILES,
    )
    location_logits = output.location_logits[0, 0].detach().cpu().numpy()
    for slot in range(NUM_HAND_SLOTS):
        legal_tiles = np.flatnonzero(placement_mask[slot])
        if legal_tiles.size == 0:
            continue
        best_tile = int(legal_tiles[np.argmax(location_logits[slot, legal_tiles])])
        candidates[slot] = slot * NUM_TILES + best_tile
    if mask[action_space.no_op_action]:
        candidates[NUM_HAND_SLOTS] = action_space.no_op_action
    if mask[action_space.ability_action]:
        candidates[NUM_HAND_SLOTS + 1] = action_space.ability_action
    if not candidates:
        raise ValueError("counterfactual state exposes no legal action type")
    return candidates


def _apply_joint_action(
    battle: BattleState,
    action_space: DiscreteTileActionSpace,
    actions: dict[int, int],
    order: tuple[int, int],
) -> dict[int, bool]:
    return {
        player_id: action_space.apply_action(
            battle,
            player_id,
            actions.get(player_id, action_space.no_op_action),
        )
        for player_id in order
    }


def counterfactual_action_scores(
    battle: BattleState,
    *,
    player_id: int,
    opponent_action: int,
    candidate_actions: dict[int, int],
    action_space: DiscreteTileActionSpace,
    horizon_ticks: int,
    continuation_model: ClasherPolicy | None = None,
    continuation_builder: StructuredObservationBuilder | None = None,
    continuation_state: tuple[Tensor, Tensor] | None = None,
    continuation_opponent: StrategyBot | None = None,
    decision_interval_ticks: int = 8,
    device: torch.device | None = None,
) -> np.ndarray:
    """Evaluate root actions over both simulator application orders.

    With continuation context, later decisions come from the frozen learner
    policy and the same deterministic opponent strategy used at collection.
    Without it, only existing troops, projectiles, buildings, status effects,
    tower fire, and root deployments evolve. Averaging both root orders removes
    the environment's simultaneous-action tie-break as a source of labels.
    """
    if player_id not in (0, 1):
        raise ValueError("counterfactual player ID must be zero or one")
    if horizon_ticks <= 0:
        raise ValueError("counterfactual horizon must be positive")
    closed_loop_values = (
        continuation_model,
        continuation_builder,
        continuation_state,
        continuation_opponent,
        device,
    )
    closed_loop = any(value is not None for value in closed_loop_values)
    if closed_loop and not all(value is not None for value in closed_loop_values):
        raise ValueError("closed-loop counterfactual context must be complete")
    if decision_interval_ticks <= 0:
        raise ValueError("counterfactual decision interval must be positive")
    scores = np.full((NUM_HAND_SLOTS + 2,), np.nan, dtype=np.float64)
    opponent_id = 1 - player_id
    for target_type, candidate_action in candidate_actions.items():
        order_scores: list[float] = []
        for order in ((0, 1), (1, 0)):
            sim = battle.clone()
            _apply_joint_action(
                sim,
                action_space,
                {player_id: candidate_action, opponent_id: opponent_action},
                order,
            )
            # A candidate is legal in the shared pre-action state, but the
            # opponent can make it fail when their simultaneous action is
            # applied first (for example by occupying the deployment tile).
            # That failed deployment is a real consequence of the randomized
            # root ordering, not a reason to drop the unfavorable branch.
            branch_state = (
                None
                if continuation_state is None
                else tuple(value.detach().clone() for value in continuation_state)
            )
            previous_action = candidate_action
            previous_reward = _advance_counterfactual_interval(
                sim,
                player_id=player_id,
                ticks=min(decision_interval_ticks, horizon_ticks),
            )
            ticks_advanced = min(decision_interval_ticks, horizon_ticks)
            while closed_loop and ticks_advanced < horizon_ticks and not sim.game_over:
                assert continuation_model is not None
                assert continuation_builder is not None
                assert branch_state is not None
                assert continuation_opponent is not None
                assert device is not None
                observation = continuation_builder.build_actor(sim, player_id)
                learner_mask = action_space.legal_action_mask(
                    sim,
                    player_id,
                    fast_path=True,
                )
                inputs = _single_actor_inputs(
                    observation,
                    learner_mask,
                    previous_action,
                    previous_reward,
                    False,
                    device,
                )
                learner_action, _, _, branch_state, _ = continuation_model.act(
                    inputs,
                    branch_state,
                    deterministic=True,
                )
                learner_action_id = int(learner_action[0, 0])
                opponent_mask = action_space.legal_action_mask(
                    sim,
                    opponent_id,
                    fast_path=True,
                )
                opponent_action_id = continuation_opponent.select_action(
                    _CounterfactualEnvView(sim, action_space),
                    opponent_id,
                    action_mask=opponent_mask,
                )
                _apply_joint_action(
                    sim,
                    action_space,
                    {
                        player_id: learner_action_id,
                        opponent_id: opponent_action_id,
                    },
                    order,
                )
                interval = min(
                    decision_interval_ticks,
                    horizon_ticks - ticks_advanced,
                )
                previous_reward = _advance_counterfactual_interval(
                    sim,
                    player_id=player_id,
                    ticks=interval,
                )
                previous_action = learner_action_id
                ticks_advanced += interval
            while not closed_loop and ticks_advanced < horizon_ticks and not sim.game_over:
                interval = min(
                    decision_interval_ticks,
                    horizon_ticks - ticks_advanced,
                )
                _advance_counterfactual_interval(
                    sim,
                    player_id=player_id,
                    ticks=interval,
                )
                ticks_advanced += interval
            p0 = counterfactual_win_prob_p0(sim)
            order_scores.append(p0 if player_id == 0 else 1.0 - p0)
        if order_scores:
            scores[target_type] = float(np.mean(order_scores))
    return scores


@dataclass
class _CounterfactualEnvView:
    battle: BattleState
    action_space: DiscreteTileActionSpace

    def get_action_mask(self, player_id: int) -> np.ndarray:
        return self.action_space.legal_action_mask(
            self.battle,
            player_id,
            fast_path=True,
        )


def _advance_counterfactual_interval(
    battle: BattleState,
    *,
    player_id: int,
    ticks: int,
) -> float:
    before = reward_potential_p0(battle, DEFENSE_V2)
    for _ in range(ticks):
        if battle.game_over:
            break
        battle.step()
    after = reward_potential_p0(battle, DEFENSE_V2)
    reward = after - before
    if battle.game_over and battle.winner is not None:
        reward += 1.0 if battle.winner == 0 else -1.0
    return float(reward if player_id == 0 else -reward)


def incoming_tower_danger(battle: BattleState, player_id: int) -> float:
    edge = potential_breakdown_p0(battle).tower_danger
    return max(0.0, -edge if player_id == 0 else edge)


def deck_key(cards: list[str]) -> str:
    return "|".join(sorted(cards))


def validate_deck_split_paths(paths: dict[str, Path]) -> dict[str, Any]:
    signatures = {
        name: {deck_key(cards) for cards in load_deck_pool(path)}
        for name, path in paths.items()
    }
    names = tuple(signatures)
    overlaps: dict[str, list[str]] = {}
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            shared = sorted(signatures[left] & signatures[right])
            if shared:
                overlaps[f"{left}:{right}"] = shared
    if overlaps:
        raise ValueError(f"counterfactual deck splits overlap: {overlaps}")
    return {
        name: {
            "path": str(paths[name].resolve()),
            "sha256": _sha256(paths[name]),
            "deck_count": len(values),
        }
        for name, values in signatures.items()
    }


def _single_actor_inputs(
    observation: ActorObservation,
    action_mask: np.ndarray,
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
    device: torch.device,
) -> PolicyInputs:
    def tensor(value: np.ndarray, dtype: torch.dtype) -> Tensor:
        return torch.as_tensor(value, dtype=dtype, device=device).view(
            1,
            1,
            *value.shape,
        )

    return PolicyInputs(
        entity_ids=tensor(observation.entity_ids, torch.long),
        entity_features=tensor(observation.entity_features, torch.float32),
        entity_mask=tensor(observation.entity_mask, torch.bool),
        hand_ids=tensor(observation.hand_ids, torch.long),
        global_features=tensor(observation.global_features, torch.float32),
        opponent_history_ids=tensor(observation.opponent_history_ids, torch.long),
        opponent_history_ages=tensor(
            observation.opponent_history_ages,
            torch.float32,
        ),
        opponent_seen_card_ids=tensor(
            observation.opponent_seen_card_ids,
            torch.long,
        ),
        action_mask=torch.as_tensor(
            action_mask,
            dtype=torch.bool,
            device=device,
        ).view(1, 1, -1),
        previous_actions=torch.tensor(
            [[previous_action]],
            dtype=torch.long,
            device=device,
        ),
        previous_rewards=torch.tensor(
            [[previous_reward]],
            dtype=torch.float32,
            device=device,
        ),
        episode_starts=torch.tensor(
            [[episode_start]],
            dtype=torch.bool,
            device=device,
        ),
    )


@torch.no_grad()
def collect_tactical_samples(
    *,
    checkpoint: Path,
    decks_path: Path,
    sampling_decks_path: Path,
    samples: int,
    seed: int,
    horizon_ticks: int,
    min_danger: float,
    min_score_margin: float,
    min_sample_gap_decisions: int,
    max_samples_per_episode: int,
    max_decisions: int,
    device: torch.device,
) -> tuple[list[TacticalSample], dict[str, Any]]:
    if min_sample_gap_decisions < 0:
        raise ValueError("minimum sample gap must be non-negative")
    if max_samples_per_episode <= 0:
        raise ValueError("maximum samples per episode must be positive")
    loaded = load_policy_checkpoint(
        checkpoint,
        device=device,
        decks_path=decks_path,
    )
    if loaded.model.config.public_seen_card_slots <= 0:
        raise ValueError("counterfactual policy requires persistent seen-card memory")
    env = SelfPlayBattleEnv(
        decision_interval_ticks=8,
        max_ticks=6000,
        decks_path=decks_path,
        sampling_decks_path=sampling_decks_path,
        seed=seed,
        canonical_perspective=True,
        engine_fast_path="on",
        reward_profile=DEFENSE_V2,
    )
    env._structured_obs_builder = loaded.builder
    strategy_names = (REACTIVE_DEFENSE, SLOW_PUSH, BALANCED)
    collected: list[TacticalSample] = []
    episode = 0
    decisions = 0
    eligible = 0
    ambiguous = 0
    illegal_labels = 0
    last_evaluation_decision = -min_sample_gap_decisions
    samples_in_episode = 0

    def reset_episode() -> tuple[int, StrategyBot, tuple[Tensor, Tensor], int, float, bool]:
        learner_player = episode % 2
        bot = StrategyBot(strategy_names[episode % len(strategy_names)])
        env.reset(seed=seed + episode * 1009)
        state = loaded.model.initial_state(1, device=device)
        return (
            learner_player,
            bot,
            state,
            env.action_space.no_op_action,
            0.0,
            True,
        )

    learner, opponent_bot, state, previous_action, previous_reward, episode_start = (
        reset_episode()
    )
    while len(collected) < samples and decisions < max_decisions:
        assert env.battle is not None
        opponent = 1 - learner
        observation = loaded.builder.build_actor(env.battle, learner)
        learner_mask = env.get_action_mask(learner)
        opponent_mask = env.get_action_mask(opponent)
        inputs = _single_actor_inputs(
            observation,
            learner_mask,
            previous_action,
            previous_reward,
            episode_start,
            device,
        )
        state_before = tuple(tensor.detach().cpu().numpy().copy() for tensor in state)
        action, _, _, next_state, output = loaded.model.act(
            inputs,
            state,
            deterministic=True,
        )
        learner_action = int(action[0, 0])
        opponent_action = opponent_bot.select_action(
            env,
            opponent,
            action_mask=opponent_mask,
        )
        danger = incoming_tower_danger(env.battle, learner)
        revealed = bool(observation.opponent_seen_card_ids.any())
        far_enough_from_last_evaluation = (
            decisions - last_evaluation_decision >= min_sample_gap_decisions
        )
        episode_has_capacity = samples_in_episode < max_samples_per_episode
        if (
            revealed
            and danger >= min_danger
            and far_enough_from_last_evaluation
            and episode_has_capacity
        ):
            last_evaluation_decision = decisions
            eligible += 1
            candidates = candidate_actions_from_output(
                output,
                learner_mask,
                env.action_space,
            )
            scores = counterfactual_action_scores(
                env.battle,
                player_id=learner,
                opponent_action=opponent_action,
                candidate_actions=candidates,
                action_space=env.action_space,
                horizon_ticks=horizon_ticks,
                continuation_model=loaded.model,
                continuation_builder=loaded.builder,
                continuation_state=next_state,
                continuation_opponent=opponent_bot,
                decision_interval_ticks=env.decision_interval_ticks,
                device=device,
            )
            finite_types = np.flatnonzero(np.isfinite(scores))
            if finite_types.size >= 2:
                ranked = finite_types[np.argsort(scores[finite_types])[::-1]]
                target = int(ranked[0])
                second = float(scores[ranked[1]])
                margin = float(scores[target] - second)
                target_action = candidates.get(target)
                if target_action is None or not learner_mask[target_action]:
                    illegal_labels += 1
                elif margin >= min_score_margin:
                    collected.append(
                        TacticalSample(
                            observation=observation,
                            action_mask=learner_mask.copy(),
                            previous_action=previous_action,
                            previous_reward=previous_reward,
                            episode_start=episode_start,
                            hidden=state_before[0][0],
                            cell=state_before[1][0],
                            target_type=target,
                            base_type=action_type(learner_action, env.action_space),
                            incoming_danger=danger,
                            candidate_scores=scores,
                            score_margin=margin,
                            episode_id=episode,
                            battle_tick=env.battle.tick,
                            learner_player=learner,
                            learner_deck_key=deck_key(env.battle.players[learner].deck),
                            opponent_deck_key=deck_key(
                                env.battle.players[opponent].deck
                            ),
                        )
                    )
                    samples_in_episode += 1
                else:
                    ambiguous += 1
        rewards, done, _ = env.step(
            {learner: learner_action, opponent: opponent_action},
            pre_action_masks={learner: learner_mask, opponent: opponent_mask},
        )
        state = next_state
        previous_action = learner_action
        previous_reward = float(rewards[learner])
        episode_start = False
        decisions += 1
        if done:
            episode += 1
            last_evaluation_decision = decisions - min_sample_gap_decisions
            samples_in_episode = 0
            learner, opponent_bot, state, previous_action, previous_reward, episode_start = (
                reset_episode()
            )
    if len(collected) < samples:
        raise RuntimeError(
            f"collected only {len(collected)} of {samples} tactical samples after "
            f"{decisions} decisions"
        )
    target_counts = np.bincount(
        np.asarray([sample.target_type for sample in collected]),
        minlength=NUM_HAND_SLOTS + 2,
    )
    return collected, {
        "samples": len(collected),
        "decisions": decisions,
        "episodes": episode + 1,
        "eligible_states": eligible,
        "ambiguous_states": ambiguous,
        "illegal_labels": illegal_labels,
        "base_type_accuracy": float(
            np.mean([sample.base_type == sample.target_type for sample in collected])
        ),
        "mean_incoming_danger": float(
            np.mean([sample.incoming_danger for sample in collected])
        ),
        "mean_score_margin": float(
            np.mean([sample.score_margin for sample in collected])
        ),
        "target_type_counts": target_counts.tolist(),
        "sampled_episodes": len({sample.episode_id for sample in collected}),
        "sampled_learner_decks": len(
            {sample.learner_deck_key for sample in collected}
        ),
        "sampled_opponent_decks": len(
            {sample.opponent_deck_key for sample in collected}
        ),
    }


def save_tactical_samples(path: Path, samples: list[TacticalSample]) -> None:
    def stack_observation(name: str) -> np.ndarray:
        return np.stack([getattr(sample.observation, name) for sample in samples])

    payload = {
        name: stack_observation(name)
        for name in (
            "entity_ids",
            "entity_features",
            "entity_mask",
            "hand_ids",
            "global_features",
            "opponent_history_ids",
            "opponent_history_ages",
            "opponent_seen_card_ids",
        )
    }
    payload.update(
        {
            "action_masks": np.stack([sample.action_mask for sample in samples]),
            "previous_actions": np.asarray(
                [sample.previous_action for sample in samples],
                dtype=np.int64,
            ),
            "previous_rewards": np.asarray(
                [sample.previous_reward for sample in samples],
                dtype=np.float32,
            ),
            "episode_starts": np.asarray(
                [sample.episode_start for sample in samples],
                dtype=np.bool_,
            ),
            "hidden": np.stack([sample.hidden for sample in samples]),
            "cell": np.stack([sample.cell for sample in samples]),
            "target_types": np.asarray(
                [sample.target_type for sample in samples],
                dtype=np.int64,
            ),
            "base_types": np.asarray(
                [sample.base_type for sample in samples],
                dtype=np.int64,
            ),
            "incoming_danger": np.asarray(
                [sample.incoming_danger for sample in samples],
                dtype=np.float32,
            ),
            "candidate_scores": np.stack(
                [sample.candidate_scores for sample in samples]
            ),
            "score_margins": np.asarray(
                [sample.score_margin for sample in samples],
                dtype=np.float32,
            ),
            "episode_ids": np.asarray(
                [sample.episode_id for sample in samples],
                dtype=np.int64,
            ),
            "battle_ticks": np.asarray(
                [sample.battle_tick for sample in samples],
                dtype=np.int64,
            ),
            "learner_players": np.asarray(
                [sample.learner_player for sample in samples],
                dtype=np.int64,
            ),
            "learner_deck_keys": np.asarray(
                [sample.learner_deck_key for sample in samples]
            ),
            "opponent_deck_keys": np.asarray(
                [sample.opponent_deck_key for sample in samples]
            ),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        np.savez_compressed(handle, **payload)


def load_tactical_arrays(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as payload:
        return {name: np.asarray(payload[name]) for name in payload.files}


def _batch_inputs(
    arrays: dict[str, np.ndarray],
    indices: np.ndarray,
    device: torch.device,
) -> tuple[PolicyInputs, tuple[Tensor, Tensor], Tensor]:
    def tensor(name: str, dtype: torch.dtype) -> Tensor:
        value = torch.as_tensor(arrays[name][indices], dtype=dtype, device=device)
        return value.unsqueeze(1)

    inputs = PolicyInputs(
        entity_ids=tensor("entity_ids", torch.long),
        entity_features=tensor("entity_features", torch.float32),
        entity_mask=tensor("entity_mask", torch.bool),
        hand_ids=tensor("hand_ids", torch.long),
        global_features=tensor("global_features", torch.float32),
        opponent_history_ids=tensor("opponent_history_ids", torch.long),
        opponent_history_ages=tensor("opponent_history_ages", torch.float32),
        opponent_seen_card_ids=tensor("opponent_seen_card_ids", torch.long),
        action_mask=tensor("action_masks", torch.bool),
        previous_actions=tensor("previous_actions", torch.long),
        previous_rewards=tensor("previous_rewards", torch.float32),
        episode_starts=tensor("episode_starts", torch.bool),
    )
    state = (
        torch.as_tensor(arrays["hidden"][indices], dtype=torch.float32, device=device),
        torch.as_tensor(arrays["cell"][indices], dtype=torch.float32, device=device),
    )
    targets = torch.as_tensor(
        arrays["target_types"][indices],
        dtype=torch.long,
        device=device,
    )
    return inputs, state, targets


def _masked_type_logits(output: PolicyOutput, action_mask: Tensor) -> Tensor:
    placement = action_mask[..., : NUM_HAND_SLOTS * NUM_TILES].reshape(
        *action_mask.shape[:-1],
        NUM_HAND_SLOTS,
        NUM_TILES,
    )
    type_mask = torch.cat(
        [placement.any(dim=-1), action_mask[..., NUM_HAND_SLOTS * NUM_TILES :]],
        dim=-1,
    )
    return output.action_type_logits.masked_fill(~type_mask, -1e9)


def counterfactual_target_distribution(
    scores: np.ndarray,
    *,
    temperature: float,
    device: torch.device,
) -> Tensor:
    if temperature <= 0.0:
        raise ValueError("counterfactual target temperature must be positive")
    values = torch.as_tensor(scores, dtype=torch.float32, device=device)
    valid = torch.isfinite(values)
    if bool((valid.sum(dim=-1) < 2).any()):
        raise ValueError("soft counterfactual targets require two candidates")
    scaled = (values / temperature).masked_fill(~valid, -1e9)
    return torch.softmax(scaled, dim=-1)


@torch.no_grad()
def evaluate_tactical_accuracy(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    *,
    device: torch.device,
    batch_size: int,
) -> dict[str, float]:
    model.eval()
    correct = 0
    loss_total = 0.0
    samples = len(arrays["target_types"])
    for start in range(0, samples, batch_size):
        indices = np.arange(start, min(samples, start + batch_size))
        inputs, state, targets = _batch_inputs(arrays, indices, device)
        logits = _masked_type_logits(model(inputs, state), inputs.action_mask)[:, 0]
        loss_total += float(nn.functional.cross_entropy(logits, targets, reduction="sum"))
        correct += int((logits.argmax(dim=-1) == targets).sum())
    return {
        "samples": float(samples),
        "type_accuracy": correct / samples,
        "type_cross_entropy": loss_total / samples,
    }


def train_counterfactual_selector(
    model: ClasherPolicy,
    anchor: ClasherPolicy,
    train: dict[str, np.ndarray],
    validation: dict[str, np.ndarray],
    *,
    device: torch.device,
    seed: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    anchor_kl_coef: float,
    target_temperature: float,
) -> tuple[list[dict[str, Any]], int]:
    trainable = []
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(name in RELATIONAL_TRAINABLE_NAMES)
        if parameter.requires_grad:
            trainable.append(parameter)
    if len(trainable) != len(RELATIONAL_TRAINABLE_NAMES):
        raise ValueError("counterfactual selector trainable scope is incomplete")
    model.to(device)
    anchor.to(device).eval()
    for parameter in anchor.parameters():
        parameter.requires_grad_(False)
    optimizer = torch.optim.AdamW(trainable, lr=learning_rate, weight_decay=1e-5)
    rng = np.random.default_rng(seed)
    best_score = (-1.0, -float("inf"))
    best_epoch = 0
    best_state: dict[str, Tensor] = {}
    rows: list[dict[str, Any]] = []
    samples = len(train["target_types"])
    for epoch in range(1, epochs + 1):
        order = rng.permutation(samples)
        model.train()
        supervised_total = kl_total = 0.0
        for start in range(0, samples, batch_size):
            indices = order[start : start + batch_size]
            inputs, state, targets = _batch_inputs(train, indices, device)
            optimizer.zero_grad(set_to_none=True)
            output = model(inputs, state)
            logits = _masked_type_logits(output, inputs.action_mask)[:, 0]
            if target_temperature > 0.0:
                target_probabilities = counterfactual_target_distribution(
                    train["candidate_scores"][indices],
                    temperature=target_temperature,
                    device=device,
                )
                supervised = -(
                    target_probabilities * torch.log_softmax(logits, dim=-1)
                ).sum(dim=-1).mean()
            else:
                supervised = nn.functional.cross_entropy(logits, targets)
            with torch.no_grad():
                anchor_logits = _masked_type_logits(
                    anchor(inputs, state),
                    inputs.action_mask,
                )[:, 0]
            anchor_probs = torch.softmax(anchor_logits, dim=-1)
            anchor_kl = (
                anchor_probs
                * (torch.log_softmax(anchor_logits, dim=-1) - torch.log_softmax(logits, dim=-1))
            ).sum(dim=-1).mean()
            loss = supervised + anchor_kl_coef * anchor_kl
            loss.backward()
            optimizer.step()
            supervised_total += float(supervised.detach()) * len(indices)
            kl_total += float(anchor_kl.detach()) * len(indices)
        validation_metrics = evaluate_tactical_accuracy(
            model,
            validation,
            device=device,
            batch_size=batch_size,
        )
        rows.append(
            {
                "epoch": epoch,
                "train_type_cross_entropy": supervised_total / samples,
                "train_anchor_type_kl": kl_total / samples,
                "validation": validation_metrics,
            }
        )
        validation_score = (
            validation_metrics["type_accuracy"],
            -validation_metrics["type_cross_entropy"],
        )
        if validation_score > best_score:
            best_score = validation_score
            best_epoch = epoch
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
    if not best_state:
        raise RuntimeError("counterfactual selector produced no checkpoint")
    model.load_state_dict(best_state)
    return rows, best_epoch


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path(
            "checkpoints/public_cycle_belief_relational_seed1049001/"
            "policy_v2_update_000040_belief.pt"
        ),
    )
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument(
        "--train-decks",
        type=Path,
        default=Path(
            "datasets/deck_curriculum_v2_seed1040001/"
            "train_without_tv_raw2000_human_meta.json"
        ),
    )
    parser.add_argument(
        "--validation-decks",
        type=Path,
        default=Path("datasets/deck_curriculum_v2_seed1040001/validation.json"),
    )
    parser.add_argument(
        "--heldout-decks",
        type=Path,
        default=Path("datasets/deck_curriculum_v2_seed1040001/heldout.json"),
    )
    parser.add_argument("--train-samples", type=int, default=256)
    parser.add_argument("--validation-samples", type=int, default=96)
    parser.add_argument("--heldout-samples", type=int, default=96)
    parser.add_argument("--horizon-ticks", type=int, default=160)
    parser.add_argument("--min-danger", type=float, default=0.01)
    parser.add_argument("--min-score-margin", type=float, default=0.002)
    parser.add_argument("--min-sample-gap-decisions", type=int, default=8)
    parser.add_argument("--max-samples-per-episode", type=int, default=8)
    parser.add_argument("--max-decisions", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=1049101)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--anchor-kl-coef", type=float, default=0.2)
    parser.add_argument("--target-temperature", type=float, default=0.0)
    parser.add_argument(
        "--action-context",
        choices=(
            "belief-only",
            "belief-board-add",
            "belief-board-interaction",
        ),
        default="belief-board-interaction",
    )
    parser.add_argument("--enemy-y-gate", type=float, default=1.0)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    split_specs = (
        ("train", args.train_decks, args.train_samples, args.seed),
        ("validation", args.validation_decks, args.validation_samples, args.seed + 1),
        ("heldout", args.heldout_decks, args.heldout_samples, args.seed + 2),
    )
    deck_splits = validate_deck_split_paths(
        {
            "train": args.train_decks,
            "validation": args.validation_decks,
            "heldout": args.heldout_decks,
        }
    )
    collection_reports: dict[str, Any] = {}
    for name, pool, count, seed in split_specs:
        path = args.corpus_root / f"{name}.npz"
        if not path.is_file():
            samples, collection = collect_tactical_samples(
                checkpoint=args.checkpoint,
                decks_path=args.decks_path,
                sampling_decks_path=pool,
                samples=count,
                seed=seed,
                horizon_ticks=args.horizon_ticks,
                min_danger=args.min_danger,
                min_score_margin=args.min_score_margin,
                min_sample_gap_decisions=args.min_sample_gap_decisions,
                max_samples_per_episode=args.max_samples_per_episode,
                max_decisions=args.max_decisions,
                device=device,
            )
            save_tactical_samples(path, samples)
            collection_reports[name] = collection
        else:
            arrays = load_tactical_arrays(path)
            collection_reports[name] = {
                "samples": len(arrays["target_types"]),
                "reused": True,
                "base_type_accuracy": float(
                    np.mean(arrays["base_types"] == arrays["target_types"])
                ),
                "target_type_counts": np.bincount(
                    arrays["target_types"],
                    minlength=NUM_HAND_SLOTS + 2,
                ).tolist(),
                "sampled_episodes": len(np.unique(arrays.get("episode_ids", np.zeros(1)))),
                "sampled_learner_decks": len(np.unique(arrays.get("learner_deck_keys", np.asarray([])))),
                "sampled_opponent_decks": len(
                        np.unique(
                            arrays.get("opponent_deck_keys", np.asarray([]))
                        )
                    ),
            }
    arrays = {
        name: load_tactical_arrays(args.corpus_root / f"{name}.npz")
        for name, *_ in split_specs
    }
    payload = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    loaded = load_policy_checkpoint(
        args.checkpoint,
        device=torch.device("cpu"),
        decks_path=args.decks_path,
    )
    config = replace(
        loaded.model.config,
        public_belief_action_context=args.action_context,
        public_belief_enemy_y_gate=args.enemy_y_gate,
    )
    model = ClasherPolicy(config, loaded.builder.card_stat_features).to(device)
    model.load_state_dict(payload["model_state_dict"])
    anchor = ClasherPolicy(config, loaded.builder.card_stat_features)
    anchor.load_state_dict(payload["model_state_dict"])
    baseline = {
        split: evaluate_tactical_accuracy(
            model,
            values,
            device=device,
            batch_size=args.batch_size,
        )
        for split, values in arrays.items()
    }
    rows, best_epoch = train_counterfactual_selector(
        model,
        anchor,
        arrays["train"],
        arrays["validation"],
        device=device,
        seed=args.seed,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        anchor_kl_coef=args.anchor_kl_coef,
        target_temperature=args.target_temperature,
    )
    final = {
        split: evaluate_tactical_accuracy(
            model,
            values,
            device=device,
            batch_size=args.batch_size,
        )
        for split, values in arrays.items()
    }
    before = payload["model_state_dict"]
    after = model.state_dict()
    changed = [name for name in before if not torch.equal(before[name].cpu(), after[name].cpu())]
    if changed != list(RELATIONAL_TRAINABLE_NAMES):
        raise ValueError(f"counterfactual fit changed unauthorized parameters: {changed}")
    output_payload = dict(payload)
    output_payload.pop("optimizer_state_dict", None)
    output_payload["model_state_dict"] = {
        name: value.detach().cpu() for name, value in after.items()
    }
    output_payload["model_config"] = config.to_dict()
    output_args = dict(payload.get("args") or {})
    output_args["public_belief_counterfactual"] = {
        "source_checkpoint": str(args.checkpoint.resolve()),
        "corpus_root": str(args.corpus_root.resolve()),
        "seed": args.seed,
        "horizon_ticks": args.horizon_ticks,
        "counterfactual_value_profile": COUNTERFACTUAL_VALUE_PROFILE,
        "counterfactual_continuation": COUNTERFACTUAL_CONTINUATION,
        "min_danger": args.min_danger,
        "min_score_margin": args.min_score_margin,
        "min_sample_gap_decisions": args.min_sample_gap_decisions,
        "max_samples_per_episode": args.max_samples_per_episode,
        "action_context": args.action_context,
        "enemy_y_gate": args.enemy_y_gate,
        "target_temperature": args.target_temperature,
        "deck_splits": deck_splits,
        "best_epoch": best_epoch,
        "trainable_names": list(RELATIONAL_TRAINABLE_NAMES),
    }
    output_payload["args"] = output_args
    args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(output_payload, args.output_checkpoint)
    report = {
        "schema_version": 1,
        "source_checkpoint": str(args.checkpoint.resolve()),
        "output_checkpoint": str(args.output_checkpoint.resolve()),
        "output_checkpoint_sha256": _sha256(args.output_checkpoint),
        "corpus_root": str(args.corpus_root.resolve()),
        "seed": args.seed,
        "horizon_ticks": args.horizon_ticks,
        "min_danger": args.min_danger,
        "min_score_margin": args.min_score_margin,
        "collection": collection_reports,
        "baseline": baseline,
        "epochs": rows,
        "best_epoch_selected_on_validation": best_epoch,
        "final": final,
        "changed_parameters": changed,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
