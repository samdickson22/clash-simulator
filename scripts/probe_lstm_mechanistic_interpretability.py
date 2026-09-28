from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F
from scipy.stats import rankdata
from torch import Tensor, nn

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.paths import decks_path as resolve_decks_path
from clasher.rl.common import NUM_TILES
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.reward_model import incoming_tower_danger, potential_breakdown_p0
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot
from clasher.rl.train_recurrent import (
    _stack_step_inputs,
    maybe_silence_stdio,
    resolve_torch_device,
)


@dataclass(frozen=True)
class ProbeResult:
    metric: float
    baseline: float
    test_samples: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe recurrent state in a trained Clasher LSTM policy"
    )
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--sampling-decks-path", default=None)
    parser.add_argument("--games-per-strategy", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1062501)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--ablation-stride", type=int, default=20)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def _ridge_predictions(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    *,
    alpha: float = 100.0,
) -> np.ndarray:
    mean = train_x.mean(axis=0, keepdims=True)
    scale = train_x.std(axis=0, keepdims=True)
    scale[scale < 1e-6] = 1.0
    x_train = (train_x - mean) / scale
    x_test = (test_x - mean) / scale
    x_train = np.concatenate(
        [x_train, np.ones((x_train.shape[0], 1), dtype=x_train.dtype)], axis=1
    )
    x_test = np.concatenate(
        [x_test, np.ones((x_test.shape[0], 1), dtype=x_test.dtype)], axis=1
    )
    penalty = np.eye(x_train.shape[1], dtype=np.float64) * alpha
    penalty[-1, -1] = 0.0
    weights = np.linalg.solve(
        x_train.T @ x_train + penalty,
        x_train.T @ train_y,
    )
    return x_test @ weights


def _r_squared(actual: np.ndarray, predicted: np.ndarray) -> float:
    residual = float(np.square(actual - predicted).sum())
    total = float(np.square(actual - actual.mean()).sum())
    return 1.0 - residual / max(total, 1e-12)


def _balanced_accuracy(actual: np.ndarray, predicted: np.ndarray) -> float:
    positive = actual == 1
    negative = ~positive
    if not positive.any() or not negative.any():
        return float("nan")
    return 0.5 * (
        float((predicted[positive] == 1).mean())
        + float((predicted[negative] == 0).mean())
    )


def _roc_auc(actual: np.ndarray, scores: np.ndarray) -> float:
    positive = actual == 1
    positive_count = int(positive.sum())
    negative_count = int((~positive).sum())
    if positive_count == 0 or negative_count == 0:
        return float("nan")
    ranks = rankdata(scores, method="average")
    rank_sum = float(ranks[positive].sum())
    return (
        rank_sum - positive_count * (positive_count + 1) / 2
    ) / (positive_count * negative_count)


def _continuous_probe(
    features: np.ndarray,
    target: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
) -> ProbeResult:
    predicted = _ridge_predictions(
        features[train_mask], target[train_mask], features[test_mask]
    )
    actual = target[test_mask]
    return ProbeResult(
        metric=_r_squared(actual, predicted),
        baseline=0.0,
        test_samples=int(actual.size),
    )


def _binary_probe(
    features: np.ndarray,
    target: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
) -> dict[str, float | int]:
    scores = _ridge_predictions(
        features[train_mask], target[train_mask], features[test_mask]
    )
    actual = target[test_mask].astype(np.int64)
    predicted = (scores >= 0.5).astype(np.int64)
    return {
        "auc": _roc_auc(actual, scores),
        "balanced_accuracy": _balanced_accuracy(actual, predicted),
        "test_samples": int(actual.size),
        "positive_rate": float(actual.mean()),
    }


def _effective_dimensions(values: np.ndarray) -> dict[str, float | int]:
    centered = values - values.mean(axis=0, keepdims=True)
    singular_values = np.linalg.svd(centered, compute_uv=False)
    variance = np.square(singular_values)
    fraction = variance / max(float(variance.sum()), 1e-12)
    cumulative = np.cumsum(fraction)
    participation_ratio = float(1.0 / max(float(np.square(fraction).sum()), 1e-12))
    return {
        "dimensions_90pct": int(np.searchsorted(cumulative, 0.90) + 1),
        "dimensions_95pct": int(np.searchsorted(cumulative, 0.95) + 1),
        "participation_ratio": participation_ratio,
    }


def _unit_correlations(
    values: np.ndarray,
    targets: dict[str, np.ndarray],
    *,
    top_k: int = 8,
) -> dict[str, list[dict[str, float | int]]]:
    standardized = values - values.mean(axis=0, keepdims=True)
    value_scale = np.sqrt(np.square(standardized).sum(axis=0)).clip(min=1e-8)
    result: dict[str, list[dict[str, float | int]]] = {}
    for name, target in targets.items():
        centered_target = target - target.mean()
        target_scale = max(float(np.sqrt(np.square(centered_target).sum())), 1e-8)
        correlation = (standardized.T @ centered_target) / (value_scale * target_scale)
        indices = np.argsort(np.abs(correlation))[-top_k:][::-1]
        result[name] = [
            {"unit": int(index), "correlation": float(correlation[index])}
            for index in indices
        ]
    return result


def _total_variation(first: Tensor, second: Tensor) -> float:
    return float(0.5 * torch.abs(first - second).sum().item())


def _write_bar_plot(
    path: Path,
    title: str,
    ylabel: str,
    names: Sequence[str],
    series: dict[str, Sequence[float]],
    *,
    floor: float | None = None,
) -> None:
    figure, axis = plt.subplots(figsize=(max(9.0, len(names) * 0.9), 5.5))
    x = np.arange(len(names))
    width = 0.8 / max(1, len(series))
    for index, (label, values) in enumerate(series.items()):
        offset = (index - (len(series) - 1) / 2) * width
        axis.bar(x + offset, values, width=width, label=label)
    if floor is not None:
        axis.axhline(floor, color="black", linewidth=1, linestyle="--")
    axis.set_xticks(x)
    axis.set_xticklabels(names, rotation=35, ha="right")
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    axis.legend()
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def main() -> None:
    args = _parse_args()
    if args.games_per_strategy <= 0:
        raise ValueError("games per strategy must be positive")
    if args.ablation_stride <= 0:
        raise ValueError("ablation stride must be positive")
    torch.set_num_threads(args.torch_threads)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = resolve_torch_device(args.device)
    checkpoint_path = Path(args.checkpoint).expanduser().resolve()
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    sampling_decks_path = (
        resolve_decks_path(args.sampling_decks_path, must_exist=True)
        if args.sampling_decks_path is not None
        else None
    )
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    loaded = load_policy_checkpoint(
        checkpoint_path,
        device=device,
        decks_path=decks_path,
    )
    model = loaded.model
    if model.config.memory_kind != "lstm" or not isinstance(model.memory, nn.LSTMCell):
        raise ValueError("checkpoint does not use an LSTMCell recurrent core")
    model.eval()
    memory = model.memory
    actor_domain = model.config.actor_observation_domain

    captured_recurrent_inputs: list[Tensor] = []

    def capture_recurrent_input(
        _module: nn.Module,
        _inputs: tuple[Tensor, ...],
        output: Tensor,
    ) -> None:
        captured_recurrent_inputs.append(output.detach())

    hook = model.recurrent_input_projection.register_forward_hook(
        capture_recurrent_input
    )
    arrays: dict[str, list[np.ndarray]] = {
        name: []
        for name in (
            "recurrent_input",
            "hidden",
            "cell",
            "input_gate",
            "forget_gate",
            "candidate_gate",
            "output_gate",
        )
    }
    labels: dict[str, list[float]] = {
        name: []
        for name in (
            "game",
            "decision",
            "time_norm",
            "own_elixir_norm",
            "opponent_elixir_norm",
            "own_tower_hp_norm",
            "opponent_tower_hp_norm",
            "incoming_danger",
            "board_value",
            "crown_diff",
            "opponent_last_play_age_norm",
            "opponent_last_play_seen",
            "opponent_cumulative_spend_norm",
            "opponent_unique_cards_seen_norm",
            "opponent_recent_play",
            "under_threat",
            "hog_in_hand",
            "policy_will_play",
            "policy_will_hog",
            "play_probability",
        )
    }
    ablation: dict[str, list[float]] = {
        key: []
        for name in ("zero_both", "zero_hidden", "zero_cell")
        for key in (f"{name}_action_changed", f"{name}_total_variation")
    }
    game_summaries: list[dict[str, Any]] = []
    start = time.perf_counter()

    try:
        game_index = 0
        for strategy_name in STRATEGY_NAMES:
            for strategy_repetition in range(args.games_per_strategy):
                matchup_seed = args.seed + game_index * 1009
                env = SelfPlayBattleEnv(
                    decision_interval_ticks=args.decision_interval,
                    max_ticks=args.max_ticks,
                    decks_path=decks_path,
                    sampling_decks_path=sampling_decks_path,
                    seed=matchup_seed,
                    canonical_perspective=True,
                    canonical_lane_globals=model.config.canonical_lane_globals,
                )
                with maybe_silence_stdio(True):
                    env.reset(seed=matchup_seed)
                assert env.battle is not None
                candidate_player = strategy_repetition % 2
                opponent_player = 1 - candidate_player
                bot = StrategyBot(strategy_name)
                state = model.initial_state(1, device=device)
                previous_action = env.action_space.no_op_action
                previous_reward = 0.0
                episode_start = True
                decision = 0
                done = False
                opponent_last_play_decision: int | None = None
                opponent_cumulative_spend = 0.0
                opponent_seen_cards: set[str] = set()
                initial_tower_hp = {
                    player_id: sum(
                        (
                            env.battle.players[player_id].left_tower_hp,
                            env.battle.players[player_id].right_tower_hp,
                            env.battle.players[player_id].king_tower_hp,
                        )
                    )
                    for player_id in (0, 1)
                }

                while not done:
                    battle = env.battle
                    assert battle is not None
                    observation = env.get_structured_observation(
                        candidate_player,
                        actor_observation_domain=actor_domain,
                    )
                    mask = env.get_action_mask(
                        candidate_player,
                        actor_observation_domain=actor_domain,
                        structured_observation=observation,
                    )
                    inputs = _stack_step_inputs(
                        [observation],
                        mask[None, :],
                        np.asarray([previous_action], dtype=np.int64),
                        np.asarray([previous_reward], dtype=np.float32),
                        np.asarray([episode_start], dtype=np.bool_),
                        device,
                        public_observation_confidence=(
                            model.config.public_observation_confidence
                        ),
                    )
                    old_hidden, old_cell = state
                    captured_recurrent_inputs.clear()
                    with torch.no_grad():
                        action_tensor, _, _, next_state, output = model.act(
                            inputs,
                            state,
                            deterministic=True,
                        )
                    if len(captured_recurrent_inputs) != 1:
                        raise RuntimeError("unexpected recurrent-input hook count")
                    recurrent_input = captured_recurrent_inputs[0][:, 0]
                    gates = F.linear(
                        recurrent_input,
                        memory.weight_ih,
                        memory.bias_ih,
                    ) + F.linear(
                        old_hidden,
                        memory.weight_hh,
                        memory.bias_hh,
                    )
                    input_gate, forget_gate, candidate_gate, output_gate = gates.chunk(
                        4, dim=-1
                    )
                    gate_values = {
                        "input_gate": torch.sigmoid(input_gate),
                        "forget_gate": torch.sigmoid(forget_gate),
                        "candidate_gate": torch.tanh(candidate_gate),
                        "output_gate": torch.sigmoid(output_gate),
                    }
                    arrays["recurrent_input"].append(
                        recurrent_input[0].detach().cpu().numpy()
                    )
                    arrays["hidden"].append(next_state[0][0].detach().cpu().numpy())
                    arrays["cell"].append(next_state[1][0].detach().cpu().numpy())
                    for name, value in gate_values.items():
                        arrays[name].append(value[0].detach().cpu().numpy())

                    candidate_action = int(action_tensor[0, 0].item())
                    candidate_state = battle.players[candidate_player]
                    opponent_state = battle.players[opponent_player]
                    own_tower_hp = sum(
                        (
                            candidate_state.left_tower_hp,
                            candidate_state.right_tower_hp,
                            candidate_state.king_tower_hp,
                        )
                    )
                    opponent_tower_hp = sum(
                        (
                            opponent_state.left_tower_hp,
                            opponent_state.right_tower_hp,
                            opponent_state.king_tower_hp,
                        )
                    )
                    breakdown = potential_breakdown_p0(battle)
                    board_value = (
                        breakdown.board_value
                        if candidate_player == 0
                        else -breakdown.board_value
                    )
                    danger = incoming_tower_danger(battle, candidate_player)
                    hand = list(candidate_state.hand)
                    candidate_slot = (
                        candidate_action // NUM_TILES
                        if candidate_action < env.action_space.no_op_action
                        else None
                    )
                    selected_card = (
                        hand[candidate_slot]
                        if candidate_slot is not None and candidate_slot < len(hand)
                        else None
                    )
                    probabilities = output.distribution().probs[0, 0]
                    play_probability = float(
                        probabilities[: env.action_space.no_op_action].sum().item()
                    )
                    age = (
                        args.max_ticks / args.decision_interval
                        if opponent_last_play_decision is None
                        else decision - opponent_last_play_decision
                    )
                    labels["game"].append(float(game_index))
                    labels["decision"].append(float(decision))
                    labels["time_norm"].append(battle.tick / args.max_ticks)
                    labels["own_elixir_norm"].append(candidate_state.elixir / 10.0)
                    labels["opponent_elixir_norm"].append(opponent_state.elixir / 10.0)
                    labels["own_tower_hp_norm"].append(
                        own_tower_hp / initial_tower_hp[candidate_player]
                    )
                    labels["opponent_tower_hp_norm"].append(
                        opponent_tower_hp / initial_tower_hp[opponent_player]
                    )
                    labels["incoming_danger"].append(danger)
                    labels["board_value"].append(board_value)
                    labels["crown_diff"].append(
                        float(
                            battle.get_crown_count(candidate_player)
                            - battle.get_crown_count(opponent_player)
                        )
                    )
                    labels["opponent_last_play_age_norm"].append(
                        min(age, 50.0) / 50.0
                    )
                    labels["opponent_last_play_seen"].append(
                        float(opponent_last_play_decision is not None)
                    )
                    labels["opponent_cumulative_spend_norm"].append(
                        opponent_cumulative_spend / 100.0
                    )
                    labels["opponent_unique_cards_seen_norm"].append(
                        len(opponent_seen_cards) / 8.0
                    )
                    labels["opponent_recent_play"].append(
                        float(opponent_last_play_decision is not None and age <= 3)
                    )
                    labels["under_threat"].append(float(danger >= 0.025))
                    labels["hog_in_hand"].append(float("HogRider" in hand))
                    labels["policy_will_play"].append(
                        float(candidate_action < env.action_space.no_op_action)
                    )
                    labels["policy_will_hog"].append(float(selected_card == "HogRider"))
                    labels["play_probability"].append(play_probability)

                    if decision >= 8 and decision % args.ablation_stride == 0:
                        baseline_probabilities = probabilities.detach()
                        zero_hidden = torch.zeros_like(old_hidden)
                        zero_cell = torch.zeros_like(old_cell)
                        variants = {
                            "zero_both": (zero_hidden, zero_cell),
                            "zero_hidden": (zero_hidden, old_cell),
                            "zero_cell": (old_hidden, zero_cell),
                        }
                        for name, variant_state in variants.items():
                            with torch.no_grad():
                                variant_action, _, _, _, variant_output = model.act(
                                    inputs,
                                    variant_state,
                                    deterministic=True,
                                )
                            variant_probabilities = variant_output.distribution().probs[
                                0, 0
                            ]
                            ablation[f"{name}_action_changed"].append(
                                float(int(variant_action[0, 0].item()) != candidate_action)
                            )
                            ablation[f"{name}_total_variation"].append(
                                _total_variation(
                                    baseline_probabilities,
                                    variant_probabilities,
                                )
                            )

                    opponent_mask = env.get_action_mask(opponent_player)
                    opponent_action = bot.select_action(
                        env,
                        opponent_player,
                        action_mask=opponent_mask,
                    )
                    opponent_hand = list(opponent_state.hand)
                    opponent_slot = (
                        opponent_action // NUM_TILES
                        if opponent_action < env.action_space.no_op_action
                        else None
                    )
                    opponent_card = (
                        opponent_hand[opponent_slot]
                        if opponent_slot is not None
                        and opponent_slot < len(opponent_hand)
                        else None
                    )
                    if opponent_card is not None:
                        opponent_seen_cards.add(opponent_card)
                        opponent_last_play_decision = decision
                        opponent_cumulative_spend += float(
                            battle.card_loader.get_card(opponent_card).mana_cost
                        )
                    with maybe_silence_stdio(True):
                        rewards, done, _ = env.step(
                            {
                                candidate_player: candidate_action,
                                opponent_player: opponent_action,
                            },
                            pre_action_masks={
                                candidate_player: mask,
                                opponent_player: opponent_mask,
                            },
                        )
                    state = next_state
                    previous_action = candidate_action
                    previous_reward = float(rewards[candidate_player])
                    episode_start = False
                    decision += 1

                assert env.battle is not None
                winner = env.battle.winner
                game_summaries.append(
                    {
                        "game": game_index,
                        "strategy": strategy_name,
                        "candidate_player": candidate_player,
                        "decisions": decision,
                        "winner": winner,
                        "candidate_outcome": (
                            "draw"
                            if winner is None
                            else "win"
                            if winner == candidate_player
                            else "loss"
                        ),
                    }
                )
                print(
                    f"game={game_index} strategy={strategy_name} "
                    f"seat={candidate_player} decisions={decision} "
                    f"outcome={game_summaries[-1]['candidate_outcome']}",
                    flush=True,
                )
                game_index += 1
    finally:
        hook.remove()

    activation_arrays = {
        name: np.asarray(values, dtype=np.float32) for name, values in arrays.items()
    }
    label_arrays = {
        name: np.asarray(values, dtype=np.float32) for name, values in labels.items()
    }
    game_ids = label_arrays["game"].astype(np.int64)
    unique_games = np.unique(game_ids)
    train_games = {int(value) for value in unique_games if int(value) % 2 == 0}
    heldout_game_train_mask = np.asarray(
        [int(value) in train_games for value in game_ids]
    )
    heldout_game_test_mask = ~heldout_game_train_mask
    decision_ids = label_arrays["decision"].astype(np.int64)
    within_trajectory_test_mask = (decision_ids + game_ids) % 5 == 0
    within_trajectory_train_mask = ~within_trajectory_test_mask
    split_protocols = {
        "within_trajectory": (
            within_trajectory_train_mask,
            within_trajectory_test_mask,
        ),
        "heldout_games": (heldout_game_train_mask, heldout_game_test_mask),
    }

    feature_sets = {
        "current_recurrent_input": activation_arrays["recurrent_input"],
        "lstm_hidden": activation_arrays["hidden"],
        "lstm_cell": activation_arrays["cell"],
    }
    continuous_targets = {
        name: label_arrays[name]
        for name in (
            "time_norm",
            "own_elixir_norm",
            "opponent_elixir_norm",
            "own_tower_hp_norm",
            "opponent_tower_hp_norm",
            "incoming_danger",
            "board_value",
            "opponent_cumulative_spend_norm",
            "opponent_unique_cards_seen_norm",
            "play_probability",
        )
    }
    binary_targets = {
        name: label_arrays[name]
        for name in (
            "opponent_last_play_seen",
            "opponent_recent_play",
            "under_threat",
            "hog_in_hand",
            "policy_will_play",
            "policy_will_hog",
        )
    }
    continuous_results: dict[str, dict[str, dict[str, Any]]] = {}
    binary_results: dict[str, dict[str, dict[str, Any]]] = {}
    age_valid = label_arrays["opponent_last_play_seen"] > 0.5
    for protocol_name, (train_mask, test_mask) in split_protocols.items():
        protocol_continuous: dict[str, dict[str, Any]] = {}
        for target_name, target in continuous_targets.items():
            protocol_continuous[target_name] = {}
            for feature_name, features in feature_sets.items():
                result = _continuous_probe(features, target, train_mask, test_mask)
                protocol_continuous[target_name][feature_name] = {
                    "r_squared": result.metric,
                    "test_samples": result.test_samples,
                }
        protocol_continuous["opponent_last_play_age_norm"] = {}
        for feature_name, features in feature_sets.items():
            result = _continuous_probe(
                features,
                label_arrays["opponent_last_play_age_norm"],
                train_mask & age_valid,
                test_mask & age_valid,
            )
            protocol_continuous["opponent_last_play_age_norm"][feature_name] = {
                "r_squared": result.metric,
                "test_samples": result.test_samples,
            }
        continuous_results[protocol_name] = protocol_continuous
        binary_results[protocol_name] = {
            target_name: {
                feature_name: _binary_probe(
                    features,
                    target,
                    train_mask,
                    test_mask,
                )
                for feature_name, features in feature_sets.items()
            }
            for target_name, target in binary_targets.items()
        }

    state_statistics: dict[str, Any] = {}
    for state_name in ("hidden", "cell"):
        values = activation_arrays[state_name]
        state_statistics[state_name] = {
            "mean": float(values.mean()),
            "std": float(values.std()),
            "mean_absolute": float(np.abs(values).mean()),
            "fraction_abs_gt_0_9": float((np.abs(values) > 0.9).mean()),
            "fraction_abs_gt_3": float((np.abs(values) > 3.0).mean()),
            **_effective_dimensions(values),
        }
    gate_statistics: dict[str, Any] = {}
    for gate_name in ("input_gate", "forget_gate", "output_gate"):
        values = activation_arrays[gate_name]
        gate_statistics[gate_name] = {
            "mean": float(values.mean()),
            "std": float(values.std()),
            "fraction_below_0_1": float((values < 0.1).mean()),
            "fraction_above_0_9": float((values > 0.9).mean()),
        }
    candidate_values = activation_arrays["candidate_gate"]
    gate_statistics["candidate_gate"] = {
        "mean": float(candidate_values.mean()),
        "std": float(candidate_values.std()),
        "fraction_abs_above_0_9": float((np.abs(candidate_values) > 0.9).mean()),
    }
    ablation_summary = {
        name: {
            "samples": len(ablation[f"{name}_action_changed"]),
            "action_change_rate": float(
                np.mean(ablation[f"{name}_action_changed"])
            ),
            "mean_total_variation": float(
                np.mean(ablation[f"{name}_total_variation"])
            ),
            "median_total_variation": float(
                np.median(ablation[f"{name}_total_variation"])
            ),
        }
        for name in ("zero_both", "zero_hidden", "zero_cell")
    }

    correlation_targets = {
        name: label_arrays[name]
        for name in (
            "time_norm",
            "own_elixir_norm",
            "opponent_elixir_norm",
            "incoming_danger",
            "board_value",
            "opponent_last_play_age_norm",
            "opponent_cumulative_spend_norm",
            "play_probability",
        )
    }
    unit_correlations = {
        state_name: _unit_correlations(
            activation_arrays[state_name], correlation_targets
        )
        for state_name in ("hidden", "cell")
    }

    elapsed = time.perf_counter() - start
    report = {
        "schema_version": 1,
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "parameter_count": int(sum(parameter.numel() for parameter in model.parameters())),
        "memory_kind": model.config.memory_kind,
        "memory_size": model.config.memory_size,
        "actor_observation_domain": actor_domain,
        "device": str(device),
        "seed": args.seed,
        "sampling_decks_path": (
            str(sampling_decks_path) if sampling_decks_path is not None else None
        ),
        "sampling_decks_sha256": (
            _sha256(sampling_decks_path) if sampling_decks_path is not None else None
        ),
        "strategies": list(STRATEGY_NAMES),
        "games_per_strategy": args.games_per_strategy,
        "games": game_summaries,
        "samples": int(game_ids.size),
        "split_protocols": {
            "within_trajectory": {
                "train_samples": int(within_trajectory_train_mask.sum()),
                "test_samples": int(within_trajectory_test_mask.sum()),
                "description": "deterministic one-in-five decision holdout within every game",
            },
            "heldout_games": {
                "train_games": sorted(train_games),
                "test_games": sorted(
                    {int(value) for value in unique_games} - train_games
                ),
                "description": "one complete seat/deck trajectory per strategy held out",
            },
        },
        "elapsed_seconds": elapsed,
        "state_statistics": state_statistics,
        "gate_statistics": gate_statistics,
        "continuous_linear_probes": continuous_results,
        "binary_linear_probes": binary_results,
        "unit_correlations": unit_correlations,
        "state_ablation": ablation_summary,
    }
    json_path = output_dir / "report.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    np.savez_compressed(
        output_dir / "activations.npz",
        **activation_arrays,
        **{f"label_{name}": value for name, value in label_arrays.items()},
    )

    for protocol_name in split_protocols:
        protocol_continuous = continuous_results[protocol_name]
        continuous_names = list(protocol_continuous)
        _write_bar_plot(
            output_dir / f"continuous_probe_r2_{protocol_name}.png",
            f"Linear decodability ({protocol_name.replace('_', ' ')})",
            "test R²",
            continuous_names,
            {
                feature_name: [
                    protocol_continuous[name][feature_name]["r_squared"]
                    for name in continuous_names
                ]
                for feature_name in feature_sets
            },
            floor=0.0,
        )
        protocol_binary = binary_results[protocol_name]
        binary_names = list(protocol_binary)
        _write_bar_plot(
            output_dir / f"binary_probe_auc_{protocol_name}.png",
            f"Binary-state probes ({protocol_name.replace('_', ' ')})",
            "test ROC AUC",
            binary_names,
            {
                feature_name: [
                    protocol_binary[name][feature_name]["auc"]
                    for name in binary_names
                ]
                for feature_name in feature_sets
            },
            floor=0.5,
        )
    gate_names = ["input_gate", "forget_gate", "output_gate"]
    _write_bar_plot(
        output_dir / "gate_statistics.png",
        "LSTM gate utilization",
        "fraction / mean",
        gate_names,
        {
            "mean": [gate_statistics[name]["mean"] for name in gate_names],
            "below 0.1": [
                gate_statistics[name]["fraction_below_0_1"] for name in gate_names
            ],
            "above 0.9": [
                gate_statistics[name]["fraction_above_0_9"] for name in gate_names
            ],
        },
    )
    ablation_names = ["zero_both", "zero_hidden", "zero_cell"]
    _write_bar_plot(
        output_dir / "state_ablation.png",
        "Causal recurrent-state ablation",
        "rate / total variation distance",
        ablation_names,
        {
            "action change rate": [
                ablation_summary[name]["action_change_rate"]
                for name in ablation_names
            ],
            "mean action-distribution TV": [
                ablation_summary[name]["mean_total_variation"]
                for name in ablation_names
            ],
        },
    )
    print(f"report={json_path}")
    print(f"samples={game_ids.size} elapsed_seconds={elapsed:.2f}")


if __name__ == "__main__":
    main()
